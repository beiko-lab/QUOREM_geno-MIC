#This is where celery-farmed tasks go to live
# These are time-intensive tasks that can be queued up and sent to another
# process
from __future__ import absolute_import, unicode_literals
import zipfile
import time
from django.template import loader
from celery import shared_task
from django.db import models, transaction
from django.apps import apps

from .formatters import guess_filetype, parse_csv_or_tsv, TableParser
from .models import *
from .artifacts import ingest_artifact

import pandas as pd
import io
import re
############### For Testing, delete later.
import time
#########################################
@shared_task
def react_to_file(upload_file_id, **kwargs):
    #something weird happens sometimes in which uploading a file doens't work.
    #it throws an ID not found error. Trying again and changing nothing seems to work
    #So, make it try twice, then throw an error if it still doesn't work.
    try:
        upfile = UploadFile.objects.get(id=upload_file_id)
    except:
        try:
        #rarely it doesn't work for no apparent reason. Sleep and try again.
            time.sleep(1)
            upfile = UploadFile.objects.get(id=upload_file_id)
        except Exception as e:
            print("error with upfile. Cannot find the file. Sys Admin should remove.")
            print(e)
    try:
        #user will recieve mail to let them know the atstus of their upload.
        mail = UserMail(user=upfile.userprofile)

        from_form = upfile.upload_type
        # S for Spreadsheet
        # A for Artifact
        status = ""
        result = None
        if from_form == "A":
            mail.title="The QIIME2 artifact you uploaded "
            print("Processing qiime file...")
            try:
                status, result = process_qiime_artifact(upfile, analysis_pk=kwargs["analysis_pk"])
            except Exception as e:
                print(e)

        elif from_form == "S":
            mail.title="The spreadsheet you uploaded "
            print("Processing table ...")
            status = process_table(upfile)
            print(status)
        else:
            mail.title="A rare error occurred with your upload."
            mail.message="The system was unable to recognize your upload file.\
                          Please double check your file selection. If this problem\
                          persists, please contact the devlopers of QUOR'em. "
            mail.save()
            upfile.upload_status = 'E'
            upfile.update()
            errorMessage = UploadMessage(file=upfile,
                                        error_message="Unidentified error with \
                                        filetype. Please contact Sys Admin.")
            errorMessage.save()
        if status == 'Success':
            mail.title += "was successfully added to QUOR'em."
            mail.message = "Your file upload completed successfully. You will now \
            be able to browse, visualize, and search for your data."
            if result:
                mail.message += "<br>"
                mail.message += "You may view the result of your upload by clicking below: <br>"
                mail.message += result.__str__()
            mail.save()
            report_success(upfile)
        else:
            mail.title += "failed."
            mail.message = "Your file upload failed. Please try again."
            mail.save()
            upfile.upload_status = 'E'
            upfile.update()
            errorMessage = UploadMessage(file=upfile, error_message="Upload failure.")
            errorMessage.save()

    except Exception as e:
        mail.title += "failed."
        mail.message = "Your file upload failed. The system gave the following error: "
        mail.message += str(e)
        mail.message += " please try reformatting your data and reuploading."
        mail.save()
        print("Except here")
        print(e)
        upfile.upload_status = 'E'
        upfile.update()
        errorMessage = UploadMessage(file=upfile, error_message=e)
        errorMessage.save()

@shared_task
def process_table(upfile):
    infile = upfile.upload_file._get_file().open()
    print("Getting logger")
    lgr = upfile.logfile.get_logger()
    print("Getting parser")
    tp = TableParser(infile)
    print("Initializing")
    for model, data in tp.initialize_generator():
        print("For %s" % (model.base_name,))
        model.initialize(data, log=lgr)
    print("Updating")
    for model, data in tp.update_generator():
        model.update(data, log=lgr)
#    print("Adding values")
#    Value.add_values(tp.value_table(), log=lgr)
    return "Success"

@shared_task
def process_qiime_artifact(upfile, analysis_pk):
    infile = upfile.upload_file._get_file().open()
    print("Getting logger")
    lgr = upfile.logfile.get_logger()
    start_time = time.time()
    analysis = Analysis.objects.get(pk=analysis_pk)
    result_uuid = ingest_artifact(infile, analysis)
    res = Result.get(name=result_uuid)
    fileval = File.get_or_create(name="uploaded_artifact", data=upfile,
                                 data_type="uploadfile", results=res)
    print("#\n#\n")
    print("~~~~~~~~~TOTAL TIME TO RUN ~~~~~~~~~~~\n#\n")
    print(time.time() - start_time)
    print("#\n#\n~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    return "Success", res[0]

@shared_task
def report_success(upfile):
    upfile.upload_status = 'S'
    #update just calls super.save() because vanilla save() has been overridden
    #to trigger a file upload process.
    upfile.update()
    #update the search vectors
    model_list = [Investigation, Sample, Feature, Process, Step, Analysis, Result, Value]
    for model in model_list:
        try:
            model.update_search_vector()
            print(model, " sv updated")
        except Exception as e:
            print(e)
            print(model, " sv didn't work")
            continue
    errorMessage = UploadMessage(file=upfile, error_message="Uploaded Successfully")
    errorMessage.save()
