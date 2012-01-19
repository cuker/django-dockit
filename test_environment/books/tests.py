import os

from django.utils import unittest
from django.contrib.auth.models import User
from django.core.files import File

from models import Author, Book, Publisher, Address, ComplexObject, SubComplexOne, SubComplexTwo

from dockit.forms import DocumentForm
from dockit.models import TemporaryDocument, create_temporary_document_class
from dockit.schema import create_document, TextField

class BookTestCase(unittest.TestCase):

    def test_monolithic(self):
        user = User.objects.create_user(username='test', email='z@z.com')
        addr = Address(street_1='10533 Reagan Rd', city='San Diego', postal_code='92126', country='US', region='CA')

        author = Author(user=user)
        author.save()

        publisher = Publisher(name='Books etc', address=addr)
        publisher.save()

        book = Book(title='Of Mice and Men', publisher=publisher)
        book.authors.append(author)
        book.save()
        book.tags.append('historical')
        book.save()

        book = Book.objects.get(book.get_id())
        assert 'historical' in book.tags
        self.assertEqual(book.title, 'Of Mice and Men')
        self.assertEqual(book.publisher.name, 'Books etc')
        self.assertEqual(book.publisher.address.city, 'San Diego')
        assert book.authors[0].user
        
        #test that modifying a nested schema is preserved
        publisher.address.street_2 = 'Apt 1'
        publisher.save()
        
        publisher = Publisher.objects.get(publisher.get_id())
        
        self.assertEqual(publisher.address.street_2, 'Apt 1')
        
        book = Book.objects.filter.tags('historical')[0]
        self.assertEqual(book.title, 'Of Mice and Men')
        
        self.assertEqual(Book.objects.filter.tags('fiction').count(), 0)
        
        self.assertEqual(publisher.dot_notation('address.country'), 'US')
        
        publisher.dot_notation_to_field('address')
        
        publisher.dot_notation_set_value('address.street_2', '# 1')
        self.assertEqual(publisher.address.street_2, '# 1')
        
        book.dot_notation_set_value('authors.0.internal_id', 'foo')
        self.assertEqual(book.authors[0].internal_id, 'foo')
    
    def test_admin(self):
        import admin
    
    def test_create_document(self):
        name = 'test'
        fields = {'title':TextField()}
        module = 'books.models'
        document = create_document(name, fields, module)
        doc = document(title='foo')
        self.assertEqual(doc.title, 'foo')
        doc.save()

class DotNotationTestCase(unittest.TestCase):
    def test_dot_notation_list_field(self):
        field = ComplexObject.dot_notation_to_field('addresses')
        self.assertEqual(field, ComplexObject.addresses)
        
        field = ComplexObject.dot_notation_to_field('addresses.*.region')
        self.assertEqual(field, Address.region)
        
        field = ComplexObject.dot_notation_to_field('addresses.*')
        self.assertEqual(field.schema, Address)
    
    def test_dot_notation_set_value(self):
        addr1 = Address(street_1='10533 Reagan Rd', city='San Diego', postal_code='92126', country='US', region='CA')
        addr2 = Address(street_1='10533 Mesane Rd', city='San Diego', postal_code='92126', country='US', region='CA')
        co = ComplexObject(field1='field1', addresses=[addr1], main_address=addr1)
        co.save()
        co.dot_notation_set_value('addresses.1', addr2)
        self.assertEqual(co.addresses[1].street_1, addr2.street_1)
        
        co.dot_notation_set_value('addresses.1.region', 'CO')
        self.assertEqual(co.addresses[1].region, 'CO')
        co.save()
        
        co.dot_notation_set_value('addresses.1.extra_data.thirdpartyid', 'ABCDEF')
        self.assertEqual(co.addresses[1].extra_data['thirdpartyid'], 'ABCDEF')
        co.save()
        
        co.dot_notation_set_value('addresses.1.extra_data.complexdict', {'foo':'bar'})
        co.dot_notation_set_value('addresses.1.extra_data.complexdict.bar', 'foo')
        self.assertTrue('bar' in co.addresses[1].extra_data['complexdict'])
        self.assertEqual(co.addresses[1].extra_data['complexdict']['bar'], 'foo')
        co.save()
        
        co.dot_notation_set_value('addresses.1.extra_data.complexdict.inception', {'level2':{}})
        co.dot_notation_set_value('addresses.1.extra_data.complexdict.inception.level2.level3', True)
        self.assertEqual(co.addresses[1].extra_data['complexdict']['inception']['level2']['level3'], True)
        co.save()
        
        co.dot_notation_set_value('addresses.1.extra_data.complexdict.inception.partners', [])
        co.dot_notation_set_value('addresses.1.extra_data.complexdict.inception.partners.0', Author(internal_id='1'))
        co.dot_notation_set_value('addresses.1.extra_data.complexdict.inception.partners.1', Author(internal_id='2'))
        #currently storing an object in a complex dict will turn it into a primitive
        self.assertEqual(co.addresses[1].extra_data['complexdict']['inception']['partners'][0]['internal_id'], '1')
        co.save()
        
        co = ComplexObject.objects.get(co.get_id())
        self.assertEqual(co.addresses[1].extra_data['complexdict']['inception']['partners'][0]['internal_id'], '1')
        
        self.assertEqual(co.dot_notation('addresses.0'), co.addresses[0])

class FormTestCase(unittest.TestCase):
    def test_form(self):
        class CustomDocumentForm(DocumentForm):
            class Meta:
                document = ComplexObject
        
        form = CustomDocumentForm(data={'field1':'hello'})
        self.assertTrue(form.is_valid(), str(form.errors))
        instance = form.save()
        self.assertEqual(instance.field1, 'hello')
        
        #test file field
        directory = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(directory, 'fixtures', 'alpaca.jpg')
        django_file = File(open(file_path, 'rb'))
        
        self.assertFalse(instance.image)
        form = CustomDocumentForm(data={'field1':'hello'}, files={'image':django_file})
        self.assertTrue(form.is_valid(), str(form.errors))
        instance = form.save()
        self.assertTrue(instance.image)
    
    def test_dotnotation_form(self):
        class CustomDocumentForm(DocumentForm):
            class Meta:
                document = ComplexObject
                dotpath = 'main_address'
        
        instance = ComplexObject(field1='field1')
        instance.save()
        data = {'street_1': '10533 Mesane Rd',
                'city': 'San Diego',
                'postal_code': '92126',
                'country': 'US',
                'region': 'CA',}
        form = CustomDocumentForm(data=data, instance=instance)
        self.assertTrue(form.is_valid(), str(form.errors))
        instance = form.save()
        self.assertEqual(instance.main_address.region, 'CA')
    
    def test_form_to_generic_document(self):
        class CustomDocumentForm(DocumentForm):
            class Meta:
                document = ComplexObject
        
        TempDoc = create_temporary_document_class(ComplexObject)
        
        instance = TempDoc(_primitive_data={'field1':'hello'})
        self.assertEqual(instance.field1, 'hello')
        self.assertEqual(instance.dot_notation('field1'), 'hello')
        
        form = CustomDocumentForm(instance=instance, data={'field1':'hello2'})
        
        self.assertEqual(form.initial['field1'], 'hello')
        self.assertTrue(form.is_valid(), str(form.errors))
        instance = form.save()
        self.assertEqual(instance._primitive_data['field1'], 'hello2')
        self.assertTrue(isinstance(instance, TempDoc))
        
        complex_obj = instance.commit_changes()
        ComplexObject.objects.get(complex_obj.pk)
        
        class CustomDocumentAddressForm(DocumentForm):
            class Meta:
                document = ComplexObject
                dotpath = 'main_address'
        
        data = {'street_1': '10533 Mesane Rd',
                'city': 'San Diego',
                'postal_code': '92126',
                'country': 'US',
                'region': 'CA',}
        form = CustomDocumentAddressForm(data=data, instance=instance)
        self.assertTrue(form.is_valid(), str(form.errors))
        instance = form.save()
        self.assertEqual(instance._primitive_data['main_address']['region'], 'CA', str(instance._primitive_data))
        self.assertTrue(isinstance(instance, TempDoc))
        
        complex_obj = instance.commit_changes(instance=complex_obj)
        ComplexObject.objects.get(complex_obj.pk)
        
        complex_obj.field1 = 'hello3'
        complex_obj.save()
        
        instance.copy_from_instance(complex_obj)
        
        self.assertEqual(instance.field1, 'hello3')
    
    def test_dotnotation_form_to_list(self):
        class CustomDocumentForm(DocumentForm):
            class Meta:
                document = ComplexObject
                dotpath = 'addresses.*'
        
        instance = ComplexObject(field1='field1')
        instance.save()
        data = {'street_1': '10533 Mesane Rd',
                'city': 'San Diego',
                'postal_code': '92126',
                'country': 'US',
                'region': 'CA',}
        form = CustomDocumentForm(data=data, instance=instance, dotpath='addresses.0')
        self.assertTrue(form.is_valid(), str(form.errors))
        instance = form.save()
        self.assertTrue(isinstance(instance.addresses[0], Address))
        self.assertEqual(instance.addresses[0].region, 'CA')
        
        form = CustomDocumentForm(instance=instance, dotpath='addresses.0')
        instance = ComplexObject.objects.get(instance.pk)
        form = CustomDocumentForm(instance=instance, dotpath='addresses.0')
        
        instance.dot_notation_set_value('addresses.0', data)
        self.assertTrue(isinstance(instance.addresses[0], Address))
        
        instance.dot_notation_set_value('addresses', [data])
        self.assertTrue(isinstance(instance.addresses[0], Address))

