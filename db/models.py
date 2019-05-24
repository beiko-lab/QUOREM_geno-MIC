from django.db import models
from django.urls import reverse
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import serializers
from django.shortcuts import redirect

#for searching
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.search import SearchVector
from django.contrib.postgres.indexes import GinIndex

from .formatters import guess_filetype, parse_csv_or_tsv, format_sample_metadata, format_protocol_sheet, format_artifact
from .parser import Upload_Handler
from .tasks import test_task, react_to_file, create_models_from_investigation_dict
import pandas as pd
import time

from celery.result import ResultBase


User = get_user_model()

#We need to wrap the auth model to make it a model the djk will work with
#It must be based on models.Model, but User is based on AbstractUser
#But this allows us to store metadata

class Investigation(models.Model):

    """
    Groups of samples, biosamples, and compsamples
    """
    name = models.CharField(max_length=255, unique=True)
    institution = models.CharField(max_length=255)
    description = models.TextField()

    #Stuff for searching
    search_vector = SearchVectorField(null=True)
    class Meta:
        indexes = [
            GinIndex(fields=['search_vector'])
        ]
    def __str__(self):
        return self.name
    #override save to update the search vector field
    def save(self, *args, **kwargs):
        sv =( SearchVector('name', weight='A') +
             SearchVector('description', weight='B') +
             SearchVector('institution', weight='C') )
        super().save(*args, **kwargs)
        Investigation.objects.update(search_vector = sv)


class UserProfile(models.Model):
    #userprofile doesnt have a search vector bc it shouldn tbe searched.
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    @classmethod
    def create(cls, user):
        userprofile = cls(user=user)
        return userprofile
    def __str__(self):
        return self.user.email

class UploadInputFile(models.Model):
    STATUS_CHOICES = (
        ('P', "Processing"),
        ('S', "Success"),
        ('E', "Error")
    )
    userprofile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, verbose_name='Uploader')
    upload_file = models.FileField(upload_to="upload/")
    upload_status = models.CharField(max_length=1, choices=STATUS_CHOICES)

    #Should upload files be indexed by the search??
    #search_vector = SearchVectorField(null=True)

    def __str__(self):
        return "UserProfile: {0}, UploadFile: {1}".format(self.userprofile, self.upload_file)

    def save(self, *args, **kwargs):
        self.upload_status = 'P'
        super().save(*args, **kwargs)
        react_to_file.delay(self.pk)
        #output = result.collect()
        ##    print(i)
    #    test_task.delay("X")
    def update(self, *args, **kwargs):
        super().save(*args, **kwargs)
    #    return reverse('uploadinputfile_detail', kwargs={'uploadinputfile_id': self.pk})

class ErrorMessage(models.Model):
    """
    Store error messages for file uploads.
    """
    uploadinputfile = models.ForeignKey(UploadInputFile, on_delete=models.CASCADE, verbose_name='Uploaded File')
    error_message = models.CharField(max_length = 1000) #???? Maybe store as a textfile????


class Sample(models.Model):
    """
    Uniquely identify a single sample (i.e., a physical sample taken at some single time and place)
    """
    name = models.CharField(max_length=255,unique=True)
    investigation = models.ForeignKey('Investigation', on_delete=models.CASCADE)  # fk 2

    search_vector = SearchVectorField(null=True)
    class Meta:
        indexes = [
            GinIndex(fields=['search_vector'])
        ]
    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        Sample.objects.update(
            search_vector = (SearchVector('name', weight= 'A') #+
                             # Should be investigation name, not pk.
                             # SearchVector('investigation', weight = 'B')
                             )
        )

class SampleMetadata(models.Model):
    """
    Stores arbitrary metadata in key-value pairs
    """
    key = models.CharField(max_length=255)
    value = models.CharField(max_length=255)
    sample = models.ForeignKey('Sample', on_delete=models.CASCADE)  # fk 3

    search_vector = SearchVectorField(null=True)
    class Meta:
        indexes = [
            GinIndex(fields=['search_vector'])
        ]
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        SampleMetadata.objects.update(
            search_vector = (SearchVector('key', weight='A') +
                              SearchVector('value', weight='B'))
        )

class BiologicalReplicate(models.Model):
    """
    A sample resulting from a biological analysis of a collected sample.
    If a poo sample is a sample, the DNA extracted and amplified with primer
    set A is a BiologicalReplicate of that sample
    """
    name = models.CharField(max_length=255,unique=True)
    sample = models.ForeignKey('Sample', on_delete=models.CASCADE, related_name='sample')  # fk 1
    sequence_file = models.ManyToManyField('Document') # store the location of the sequence file(s)
    biological_replicate_protocol = models.ForeignKey('BiologicalReplicateProtocol', on_delete=models.CASCADE)  # fk 5
    #Should be locked down to match sample's Investigation field, but I can't
    investigation = models.ForeignKey('Investigation', on_delete=models.CASCADE)

    search_vector = SearchVectorField(null=True)
    class Meta:
        indexes = [
            GinIndex(fields=['search_vector'])
        ]
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        BiologicalReplicate.objects.update(
            search_vector = (SearchVector('name', weight='A') #+
                            #  SearchVector('sample', weight='B') +
                            # SearchVector should use the sample NAME, not id. will need to query it....
                            # SearchVector('biological_replicate_protocol', weight='D') #+
                              #SearchVector('investigation', weight='C')
                              )
        )
class BiologicalReplicateMetadata(models.Model):
    """
    Metadata for the biological sample (PCR primers, replicate #, storage method, etc.)
    Basically anything that could change between a Sample and a BiologicalReplicate
    goes in here
    """
    key = models.CharField(max_length=255)
    value = models.CharField(max_length=255)
    biological_replicate = models.ForeignKey('BiologicalReplicate', on_delete=models.CASCADE) # fk 14

    search_vector = SearchVectorField(null=True)
    class Meta:
        indexes = [
            GinIndex(fields=['search_vector'])
        ]
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        BiologicalReplicateMetadata.objects.update(
            search_vector = (SearchVector('key', weight='A') +
                              SearchVector('value', weight='B')#+
                             # SearchVector('BiologicalReplicate', weight='C')
                             )
        )

class Document(models.Model):  #file
    """
    Store information to locate arbitrary files
    """
    md5_hash = models.CharField(max_length=255)
    document = models.FileField()
    #We can get size and location through the FileSystem manager in Django


class ProtocolParameterDeviation(models.Model):
    """
    Keep track of when a BiologicalReplicate isn't done exactly as SOP
    """
    # Identifies which replicate is deviating
    biological_replicate = models.ForeignKey('BiologicalReplicate', on_delete=models.CASCADE)  # fk 9
    # Stores the default
    protocol_step = models.ForeignKey('ProtocolStep', on_delete=models.CASCADE) # fk ??
    # Comment expanding on what the deviation was
    description = models.TextField()
    # Stores the deviation from the default
    value = models.TextField()


class BiologicalReplicateProtocol(models.Model):
    """
    A list of the steps that the biological sample was processed with
    """
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField()
    citation = models.TextField() # should we include citations, or just have that in description?
#    protocol_steps = models.ManyToManyField('ProtocolStep')

    search_vector = SearchVectorField(null=True)
    class Meta:
        indexes = [
            GinIndex(fields=['search_vector'])
        ]
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        BiologicalReplicateProtocol.objects.update(
            search_vector = (SearchVector('name', weight='A') +
                             SearchVector('citation', weight='B') +
                             SearchVector('description', weight='C'))
        )
class ProtocolStep(models.Model):
    """
    Names and descriptions of the protocol steps and methods, e.g., stepname = 'amplification', method='pcr'
    """
    biological_replicate_protocols = models.ManyToManyField('BiologicalReplicateProtocol', blank=True)
    name = models.CharField(max_length=255)
    method = models.CharField(max_length=255)
    def __str__(self):
        return '%s -> %s' % (self.name, self.method)

"""
def protocol_step_from_table(intable):
    count = 0
    pks = [] #keys of created protocols
    for index, row in intable.iterrows():
        #table should have columns 'step' and 'method'
        protocolStep = ProtocolStep(name=row['step'], method=row['method'])
        protocolStep.save()
        count += 1
    print("Added ", count, " entries to table ProtocolStep")
"""
class ProtocolStepParameter(models.Model):
    """
    The default parameters for each protocol step
    """
    protocol_step = models.ForeignKey('ProtocolStep',
                                             on_delete=models.CASCADE, verbose_name="Protocol Step") # fk ??
    name = models.CharField(max_length=255)
    value = models.CharField(max_length=255)
    description = models.TextField(blank=True)

#####TODO Ensure ProtocolStep and ProtocolStepParameter are made at the same time, share keys where needed
"""
def protocol_step_parameter_from_table(intable):
    count = 0

    for index, row in intable.iterrows():
        #table should have 'step', 'method', 'description', 'parameter_name', and 'parameter_default'
        protocolStepParameter = ProtocolStepParameter(protocol_step=fks[count], name='
"""

class ProtocolStepParameterDeviation(models.Model):
    """
    The deviations from the defaults, attached to a specific Replicate
    """
    protocol_step_parameter = models.ForeignKey('ProtocolStepParameter', on_delete=models.CASCADE)
    biological_replicate = models.ForeignKey('BiologicalReplicate', on_delete=models.CASCADE)
    new_value = models.CharField(max_length=255)
    comment = models.TextField(blank=True)

class PipelineResult(models.Model):
    """
    Some kind of result from a ComputationalPipeline
    """
    document = models.ManyToManyField('Document')
    computational_pipeline = models.ForeignKey('ComputationalPipeline', on_delete=models.CASCADE)
    pipeline_step = models.ForeignKey('PipelineStep', on_delete=models.CASCADE)
    replicates = models.ManyToManyField('BiologicalReplicate')


class PipelineDeviation(models.Model):
    """
    Keep track of when an object's provenance involves deviations in the listed SOP
    """
    pipeline_result = models.ForeignKey('PipelineResult', on_delete=models.CASCADE)  # fk 11
    pipeline_parameter = models.ForeignKey('PipelineParameter', on_delete=models.CASCADE) # fk ??
    value = models.CharField(max_length=255)


class ComputationalPipeline(models.Model):
    """
    Stores the steps and default parameters for a pipeline
    """
    pipeline_step = models.ManyToManyField('PipelineStep') # fk 12


class PipelineStep(models.Model):
    """
    Describes a single step in the computational pipeline.
    These can be programatically defined by QIIME's transformations.
    """
    # many to many
    name = models.CharField(max_length=255)


class PipelineParameter(models.Model):
    """
    The default parameters for each step, for this pipeline
    """
    computational_pipeline = models.ForeignKey('ComputationalPipeline', on_delete=models.CASCADE) # fk ??
    pipeline_step = models.ForeignKey('PipelineStep', on_delete=models.CASCADE)  # fk 13
    value = models.CharField(max_length=255)
    key = models.CharField(max_length=255)


##Function for search.
##Search returns a list of dicts. Get the models from the dicts.
def load_mixed_objects(dicts,model_keys):
    #dicts are expected to have 'pk', 'rank', 'type'
    to_fetch = {}
    for d in dicts:
        to_fetch.setdefault(d['type'], set()).add(d['pk'])
    fetched = {}
    #TODO: Refactor this to be the same maping used in views.py
    """
    for key, model in(
        ('investigation', Investigation),
        ('sample', Sample),
        ('sampleMetadata', SampleMetadata),
    ):
    """
    for key, model in model_keys:
        ids = to_fetch.get(key) or []
        objects = model.objects.filter(pk__in=ids)
        for obj in objects:
            fetched[(key, obj.pk)] = obj
    #return the list in the same otder as dicts arg
    to_return = []
    for d in dicts:
        item = fetched.get((d['type'], d['pk'])) or None
        if item:
                item.original_dict = d
        to_return.append(item)

    return to_return
