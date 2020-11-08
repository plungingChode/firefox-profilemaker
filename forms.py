from copy import Error
from django import forms
from django.forms.forms import Form
from django.utils.html import conditional_escape
from django.utils.translation import ugettext as _
from django.utils.safestring import mark_safe
import json, glob, os

from .merge import merge

# current structure:
# - FirefoxTracking: builtin features, which send data to Mozilla,
#   google and other thirdparties
# - WebsiteTracking: Features, which are made for tracking (i.e. ping, beacons)
#   or may used for it (i.e. battery api)
# - Privacy: General privacy related settings like referer, cookies, etc.
#   which may be harmless or needed (i.e. cookies)
# - Security: No direct privacy problems, but maybe security issues
#   (i.e. webgl may hang Firefox)
# - Bloatware: Settings, which disable unwanted features like hello or pocket
# - Annoyances: Settings, which disable first-run
#   "did you know, here is our new tab page" popups.
#
# TODO: WebsiteTracking could be split into Tracking (ping, beacon, ...) and
#       Fingerprinting (battery, canvas, ...), when there are more settings.

class CustomCheckbox(forms.CheckboxInput):
    template_name = "checkbox.html"

class CustomBoolField(forms.BooleanField):
    widget = CustomCheckbox

    def __init__(self, *, breaks=None, **kwargs):
        self.breaks = breaks
        super(CustomBoolField, self).__init__(**kwargs)

class CustomChoiceField(forms.ChoiceField):
    def __init__(self, *, breaks=None, **kwargs):
        self.breaks = breaks
        super(CustomChoiceField, self).__init__(**kwargs)

class CustomCharField(forms.CharField):
    def __init__(self, *, breaks=None, **kwargs):
        self.breaks = breaks
        super(CustomCharField, self).__init__(**kwargs)

class ConfigForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super(ConfigForm, self).__init__(*args, **kwargs)
        self.fields['form_name'] = forms.CharField(initial=self.id, widget=forms.widgets.HiddenInput)
        for option in self.options:
            if option['type'] == "boolean":
                self.fields[option['name']] = CustomBoolField(
                    label=option['label'],
                    label_suffix='',
                    help_text=option['help_text'],
                    initial=option['initial'], required=False,
                    breaks=option.get('breaks'))
            if option['type'] == "choice":
                choices = option['choices']
                self.fields[option['name']] = CustomChoiceField(
                    label=option['label'],
                    label_suffix='',
                    help_text=option['help_text'],
                    choices = list(enumerate(choices)),
                    initial=option['initial'], required=False,
                    breaks=option.get('breaks'))
            elif option['type'] == "text":
                self.fields[option['name']] = CustomCharField(
                    label=option['label'],
                    label_suffix='',
                    help_text=option['help_text'],
                    initial=option['initial'], required=False,
                    breaks=option.get('breaks'))

    def _html_output(self, normal_row, error_row, row_ender, help_text_html, errors_on_separate_row):
        "Output HTML. Used by as_table(), as_ul(), as_p()."

        # Errors that should be displayed above all fields.
        top_errors = self.non_field_errors().copy()
        output, hidden_fields = [], []

        for name, field in self.fields.items():
            html_class_attr = ''
            bf = self[name]
            bf_errors = self.error_class(bf.errors)
            if bf.is_hidden:
                if bf_errors:
                    top_errors.extend(
                        [_('(Hidden field %(name)s) %(error)s') % {'name': name, 'error': str(e)}
                         for e in bf_errors])
                hidden_fields.append(str(bf))
            else:
                if errors_on_separate_row and bf_errors:
                    output.append(error_row % str(bf_errors))

                if bf.label:
                    label = conditional_escape(bf.label)
                    
                    # Render labeled stuff inside label, and show
                    # checkbox on right
                    if field.widget.input_type == 'checkbox':
                        label = bf.label_tag(str(bf) + label, { 'class': 'bool' }) or ''
                    else:
                        label = bf.label_tag(label + str(bf)) or ''
                else:
                    label = ''

                # Render `breaks` warning as list
                breaks = ''
                if field.breaks:
                    callout_local = 'This setting may break:' # TODO localize string
                    affects_local = 'It affects:' # TODO localize string

                    # TODO maybe replace w/ class field + .html template?
                    breaks_template = """
                        <div class="info block">
                            <h5>%(icon)s %(callout)s %(type)s</h5>
                            <span class="desc">%(desc)s</span>
                            <div>%(affects)s
                                <ul>%(what)s</ul>
                            </div>
                        </div>"""

                    what = ''
                    for b in field.breaks['what']:
                        what += '<li>%s</li>' % b

                    breaks = breaks_template % { 
                        'icon': '[ !! ]', # TODO replace w/ actual icon?
                        'callout': callout_local,
                        'desc': field.breaks['description'],
                        'type': field.breaks['type'],
                        'affects': affects_local,
                        'what': what 
                    }

                # Create a 'class="..."' attribute if the row should have any
                # CSS classes applied.
                css_classes = bf.css_classes()
                if css_classes:
                    html_class_attr = ' class="%s"' % css_classes

                if field.help_text:
                    help_text = help_text_html % field.help_text
                else:
                    help_text = ''

                output.append(normal_row % {
                    'errors': bf_errors,
                    'label': '',
                    'field': label if bf.label else bf,
                    'breaks': breaks,
                    'help_text': help_text,
                    'html_class_attr': html_class_attr,
                    'css_classes': css_classes,
                    'field_name': bf.html_name,
                })

        if top_errors:
            output.insert(0, error_row % top_errors)

        if hidden_fields:  # Insert any hidden fields in the last row.
            str_hidden = ''.join(hidden_fields)
            if output:
                last_row = output[-1]
                # Chop off the trailing row_ender (e.g. '</td></tr>') and
                # insert the hidden fields.
                if not last_row.endswith(row_ender):
                    # This can happen in the as_p() case (and possibly others
                    # that users write): if there are only top errors, we may
                    # not be able to conscript the last row for our purposes,
                    # so insert a new, empty row.
                    last_row = (normal_row % {
                        'errors': '',
                        'label': '',
                        'field': '',
                        'help_text': '',
                        'breaks': '',
                        'html_class_attr': html_class_attr,
                        'css_classes': '',
                        'field_name': '',
                    })
                    output.append(last_row)
                output[-1] = last_row[:-len(row_ender)] + str_hidden + row_ender
            else:
                # If there aren't any rows in the output, just append the
                # hidden fields.
                output.append(str_hidden)
        return mark_safe('\n'.join(output))

    def as_p(self):
        "Cannot render with <p> tags, since the `breaks` list would end the tag"
        raise Error("Cannot render form as <p>")

    # as_table & as_ul: Same as super's, but include `breaks` field
    def as_table(self):
        "Return this form rendered as HTML <tr>s -- excluding the <table></table>."
        return self._html_output(
            normal_row='<tr%(html_class_attr)s><th>%(label)s</th><td>%(errors)s%(field)s%(help_text)s%(breaks)s</td></tr>',
            error_row='<tr><td colspan="2">%s</td></tr>',
            row_ender='</td></tr>',
            help_text_html='<br><span class="helptext">%s</span>',
            errors_on_separate_row=False,
        )

    def as_ul(self):
        "Return this form rendered as HTML <li>s -- excluding the <ul></ul>."
        return self._html_output(
            normal_row='<li%(html_class_attr)s>%(errors)s%(label)s %(field)s%(help_text)s%(breaks)s</li>',
            error_row='<li>%s</li>',
            row_ender='</li>',
            help_text_html=' <span class="helptext">%s</span>',
            errors_on_separate_row=False,
        )
    
    def as_div(self):
        """
        Return this form rendered as HTML <div>s -- excluding the <div></div>.
        Currently this is the only fully styled rendering mode.
        """
        return self._html_output(
            normal_row='<div%(html_class_attr)s>%(errors)s%(label)s %(field)s%(help_text)s%(breaks)s</div>',
            error_row='<div>%s</div>',
            row_ender="</div>",
            help_text_html=' <span class="helptext">%s</span>',
            errors_on_separate_row=False,
        )


    def get_config_and_addons(self):
        config = {}
        addons = []
        files_inline = {}
        enterprise_policy = {}
        if self.is_valid():
            for option in self.options:
                if option['type'] == "boolean":
                    if self.cleaned_data[option['name']]:
                        for key in option['config']:
                            config[key] = option['config'][key]
                        if "addons" in option:
                            addons += option['addons']
                        if 'files_inline' in option:
                            files_inline.update(option['files_inline'])
                        enterprise_policy = merge(enterprise_policy, option.get('enterprise_policy', {}))
                elif option['type'] == "choice":
                    choice = int(self.cleaned_data[option['name']])
                    for key in option['config'][choice]:
                        config[key] = option['config'][choice][key]
                    if "addons" in option:
                        addons += option['addons'][choice]
                    if 'files_inline' in option:
                        files_inline.update(option['files_inline'][choice])
                    enterprise_policy = merge(enterprise_policy, option.get('enterprise_policy', {}))
                elif option['type'] == "text":
                    if option.get('blank_means_default', False) and self.cleaned_data[option['name']] == "":
                        continue
                    else:
                        config[option['setting']] = self.cleaned_data[option['name']]
                    # TODO: support text fields for enterprise policies

        return config, addons, files_inline, enterprise_policy

def create_configform(id, name, options):
    class DynamicConfigForm(ConfigForm):
        pass
    DynamicConfigForm.id=id
    DynamicConfigForm.name=name
    DynamicConfigForm.options=options
    return DynamicConfigForm


PROFILES = {}
settings_path = os.path.dirname(__file__) + "/settings"
profiles_path = os.path.dirname(__file__) + "/profiles"
profile_files = glob.glob(profiles_path + "/*.json")
for profile_file in profile_files:
    profile_name, profile = json.load(open(profile_file, "r"))
    items = {}
    for category in profile:
        options = []
        for file in profile[category]:
            data = json.load(open(settings_path + "/" + file, "r"))
            for item in data:
                item['label'] = _(mark_safe(item['label']) or "")
                item['help_text'] = _(item['help_text'] or "")
                if item.get("enterprise_policy_only", False):
                    if item.get('help_text'):
                        item['help_text'] += "<br /><i>" + _("(enterprise policy download only)") + "</i>"
                    else:
                        item['help_text'] += "<i>" + _("(enterprise policy download only)") + "</i>"
            options += data
        items[category] = options
    form_list = []
    for idx, name in enumerate(items):
        form_list.append(create_configform(id="form{0:d}".format(idx), name=name, options=items[name]))
    PROFILES[os.path.basename(profile_file)] = [profile_name, form_list]
