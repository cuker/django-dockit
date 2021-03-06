from common import Manifest

from django.core import serializers as django_serializers
from dockit.core import serializers as dockit_serializers

class DjangoFixtureManifest(Manifest):
    def load(self):
        results = list()
        for data_source in self.data_sources:
            data = data_source.get_data()
            for obj in django_serializers.deserialize('python', data):
                obj.save()
                results.append(obj)
        return results
    
    @classmethod
    def dump(cls, objects, data_source, data_source_key, **options):
        data = django_serializers.serialize('python', objects)
        results = data_source.to_payload(data_source_key, data, **options)
        return {'data': [results]}

class DockitFixtureManifest(Manifest):
    def load(self):
        return self.load_from_data_sources(self.data_sources)
    
    def load_from_data_sources(self, data_sources):
        results = list()
        for data_source in data_sources:
            data = data_source.get_data()
            for obj in dockit_serializers.deserialize('python', data):
                obj = self.save_object(obj)
                if obj is not None:
                    results.append(obj)
        return results
    
    def save_object(self, obj):
        obj.save()
        return obj
    
    @classmethod
    def dump(cls, objects, data_source, data_source_key, **options):
        data = dockit_serializers.serialize('python', objects)
        results = data_source.to_payload(data_source_key, data, **options)
        return {'data': [results]}

