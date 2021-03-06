import cgi
import colour
from collections import OrderedDict

from django.db import models
from django.apps import apps
from django import forms

#for searching
from django.contrib.postgres.search import SearchVector
from django.contrib.postgres.aggregates import StringAgg
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from db.models.object import Object
from db.models.value import Value
from django.utils.html import format_html, mark_safe


class Feature(Object):
    base_name = "feature"
    plural_name = "features"

    gv_node_style = {'style': 'rounded,filled', 'shape': 'box', 'fillcolor': '#ff5497'}
    node_height = 5
    node_width = 7
    grid_fields = ["name", "samples"]

    description = "A Feature represents something that is being tracked across Samples, such as a taxonomic group, a functional gene, or a molecule"

    name = models.CharField(max_length=255, verbose_name="Name")

    values = models.ManyToManyField('Value', related_name="features", blank=True)

    @classmethod
    def get_display_value(cls, obj, field):
        if field == "name":
            return obj.get_detail_link()
        elif field == "samples":
            if not obj.samples.exists():
                return "No observations recorded"
            elif obj.samples.all().count() >= 10:
                return mark_safe("<BR/>".join([str(x) for x in obj.samples.all()[0:10]] + ["... %d more" % (obj.samples.all().count()-10,)]))
            else:
                return mark_safe("<BR/>".join([str(x) for x in obj.samples.all()]))

    @classmethod
    def add_to_annotations(cls, name, value_type=None):
        if value_type is None:
            value_type = Value # This will add all subclasses of Values too, I think
        else:
            value_type = Value.get_value_types(type_name=value_type)
        signatures = DataSignature.objects.filter(name=name, value_type=ContentType.objects.get_for_model(value_type))
        for feat in features:
            feat.annotations.add(*feat.values.instance_of(value_type).prefetch_related("signature").filter(signature__name=name))

    def related_samples(self, upstream=False):
        #SQL Depth: 1
        samples = self.samples.all()
        if upstream:
            samples = samples | apps.get_model("db", "Sample").objects.filter(pk__in=self.samples.values("all_upstream").distinct())
        return samples

    def related_results(self, upstream=False):
        # SQL Depth: 2
        results = self.results.all()
        if upstream:
            results = results | apps.get_model("db", "Result").objects.filter(pk__in=results.values("all_upstream").distinct())
        return results

    def html_samples(self):
        sample_count = self.samples.count()
        accordions = {'samples': {'heading': format_html('Show Samples ({})', str(sample_count))}}
        content = ""
        for sample in self.samples.all():
            content += format_html("{}<BR/>", mark_safe(str(sample)))
        accordions['samples']['content'] = content
        return self._make_accordion("samples", accordions)

    def get_node_attrs(self, show_values=True, highlight=False):
        htm = "<<table border=\"0\"><tr><td colspan=\"2\"><b>%s</b></td></tr>" % (self.base_name.upper(),)
        if not show_values:
           sep = ""
        else:
           sep = "border=\"1\" sides=\"b\""
        htm += "<tr><td colspan=\"2\" %s><b><font point-size=\"18\">%s</font></b></td></tr>" % (sep, str(getattr(self, self.id_field)))
        if show_values:
            val_types = apps.get_model("db.Value").get_value_types()
            val_counts = []
            for vtype in val_types:
                count = self.values.instance_of(vtype).count()
                val_counts.append((vtype.base_name.capitalize(), count))
            if len(val_counts) > 0:
                htm += "<tr><td><i>Type</i></td><td><i>Count</i></td></tr>"
                for vtype, count in val_counts:
                    if count == 0:
                        continue
                    htm += "<tr><td border=\"1\" bgcolor=\"#ffffff\">%s</td>" % (vtype,)
                    htm += "<td border=\"1\" bgcolor=\"#ffffff\">%d</td></tr>" % (count,)
            for data_type_pk in data_types:
                data_type = ContentType.objects.get_for_id(data_type_pk).model_class()
            htm += "<tr><td colspan=\"2\"></td></tr>"
        htm += "</table>>"
        
        
        attrs = self.gv_node_style
        attrs["name"] = str(self.pk)
        attrs["label"] = htm
        attrs["fontname"] = "FreeSans"
        attrs["href"] = reverse(self.base_name + "_detail",
                                kwargs={self.base_name+"_id":self.pk})
        if not highlight:
            col = colour.Color(attrs["fillcolor"])
        else:
            black= colour.Color('black')
            col = colour.Color(attrs["fillcolor"])
            col = list(col.range_to(black, 10))[1]
            attrs['penwidth'] = "3"
        attrs['fillcolor'] = col.hex_l
        return attrs

    @classmethod
    def get_display_form(cls):
        from django_jinja_knockout.widgets import DisplayText
        ParentDisplayForm = super().get_display_form()
        class DisplayForm(ParentDisplayForm):
            sample_accordion = forms.CharField(widget=DisplayText(), label="Samples")
            node = None #Cheating way to override parent's Node and hide it
            class Meta:
                model = cls
                exclude = ['search_vector', 'values']
            def __init__(self, *args, **kwargs):
                if kwargs.get('instance'):
                    kwargs['initial'] = OrderedDict()
                    kwargs['initial']['sample_accordion'] = mark_safe(kwargs['instance'].html_samples())
                super().__init__(*args, **kwargs)
                self.fields.move_to_end("value_accordion")
        return DisplayForm
    
    
