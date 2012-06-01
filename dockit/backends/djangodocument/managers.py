from django.db import models

from dockit.schema.common import DotPathTraverser, DotPathNotFound

class DocumentManager(models.Manager):
    pass

class RegisteredIndexManager(models.Manager):
    def __init__(self, *args, **kwargs):
        super(RegisteredIndexManager, self).__init__(*args, **kwargs)
        self.index_models = dict()
    
    def register_index_model(self, key, model, instance_types):
        self.index_models[key] = {'model':model,
                                  'instance_types':instance_types}
    
    def get_index(self, key):
        return self.index_models[key]
    
    def get_index_for_value(self, value):
        for entry in self.index_models.itervalues():
            if isinstance(value, entry['instance_types']):
                return entry['model']
        assert False, str(type(value))
        return None
    
    def get_query_index_name(self, query_index):
        if query_index.name:
            return query_index.name
        return str(query_index._index_hash())
    
    def remove_index(self, query_index):
        name = self.get_query_index_name(query_index)
        collection = query_index.collection
        return self.filter(name=name, collection=collection).delete()
    
    def register_index(self, query_index):
        name = self.get_query_index_name(query_index)
        collection = query_index.collection
        #TODO the rest should be done in a task
        query_hash = query_index._index_hash()
        obj, created = self.get_or_create(name=name, collection=collection, defaults={'query_hash':query_hash})
        if not created:
            if obj.query_hash == query_hash:
                return
            obj.query_hash = query_hash
            for index in self.index_models.itervalues():
                index['model'].objects.filter(document__index=obj).delete()
            obj.save()
        
        #TODO do a reindex in a task
        documents = obj.get_document().objects.all()
        for doc in documents:
            self.evaluate_query_index(obj, query_index, doc.pk, doc.to_python(doc))
    
    def on_save(self, collection, doc_id, data, encoded_data=None):
        from dockit.backends import INDEX_ROUTER
        registered_queries = self.filter(collection=collection)
        for query in registered_queries:
            query_index = INDEX_ROUTER.registered_querysets[collection][query.query_hash]
            self.evaluate_query_index(query, query_index, doc_id, data)
    
    def on_delete(self, collection, doc_id):
        from models import RegisteredIndexDocument
        RegisteredIndexDocument.objects.filter(index__collection=collection, doc_id=doc_id).delete()
    
    def evaluate_query_index(self, registered_index, query_index, doc_id, data):
        from models import RegisteredIndexDocument
        
        #evaluate if document passes filters
        for inclusion in query_index.inclusions:
            dotpath = inclusion.dotpath()
            traverser = DotPathTraverser(dotpath)
            try:
                traverser.resolve_for_raw_data(data)
            except DotPathNotFound:
                return False
            if traverser.current_value != inclusion.value:
                return False
        for exclusion in query_index.exclusions:
            dotpath = exclusion.dotpath()
            traverser = DotPathTraverser(dotpath)
            try:
                traverser.resolve_for_raw_data(data)
            except DotPathNotFound:
                pass
            else:
                if traverser.current_value == exclusion.value:
                    return False
        
        #index params
        index_doc, created = RegisteredIndexDocument.objects.get_or_create(index=registered_index, doc_id=doc_id)
        for param in query_index.indexes:
            dotpath = param.dotpath()
            traverser = DotPathTraverser(dotpath)
            try:
                traverser.resolve_for_raw_data(data)
            except DotPathNotFound:
                value = None
            else:
                value = traverser.current_value
            index_model = self.get_index_for_value(value) #TODO if value is None there is ambiguity, use schema to resolve this
            #now create a BaseIndex entry associated to a registered index document
            index_model.objects.db_index(index_doc, param.key, value)

class BaseIndexManager(models.Manager):
    def filter_kwargs_for_operation(self, operation):
        if operation.key in ('pk', '_pk'):
            return {'pk__%s' % operation.operation: operation.value}
        prefix = self.model._meta.get_field('document').related.var_name
        filter_kwargs = dict()
        filter_kwargs['%s__param_name' % prefix] = operation.key
        filter_kwargs['%s__value__%s' % (prefix, operation.operation)] = operation.value
        return filter_kwargs
    
    def unique_values(self, index):
        return self.filter(param_name=index).values_list('value', flat=True).distinct()
    
    def clear_db_index(self, index_document, param_name=None):
        if param_name is None:
            return self.filter(document=index_document).delete()
        return self.filter(document=index_document, param_name=param_name).delete()
    
    def db_index(self, index_document, param_name, value):
        self.filter(document=index_document, param_name=param_name).delete()
        from dockit.schema import Document
        if isinstance(value, models.Model):
            value = value.pk
        if isinstance(value, Document):
            value = value.pk
        obj = self.create(document=index_document, param_name=param_name, value=value)

