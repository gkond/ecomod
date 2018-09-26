from flask import Flask, render_template, request, jsonify
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms import IntegerField, FloatField, DateField, SelectField, \
    SelectMultipleField, FieldList, FormField, validators
from datetime import datetime
import os.path
import json
import re
import pprint

pp = pprint.PrettyPrinter(indent=4)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
Bootstrap(app)


def load_json(name):
    filename = os.path.join(app.static_folder, name)
    return json.load(open(filename))


@app.route('/')
def view_home():
    return render_template('home.html')


@app.route('/models')
def view_models():
    models = load_json('models.json')
    return render_template('models.html', models=models)


@app.route('/results')
def view_results():
    results = load_json('results.json')
    time_series = []
    for name, values in results.items():
        ts = {
            'id': name,
            'values': {
                'x': [],
                'y': []
            }
        }
        for key, value in values.items():
            ts['values']['x'].append(key)
            ts['values']['y'].append(value)

        # Input time series. Examples:
        # G & A_Exxon_sovcombank: macbook:timeseries
        # oil_Brent: macbook:timeseries
        # Income_tax_rate: macbook:timeseries
        if re.search(':timeseries$', name):
            attrs = name.split(':')
            (ts_name, ts_author), rest = attrs[:2], attrs[2:]
            ts['result_type'] = 'Input time series'
            ts['ts_name'] = ts_name
            ts['ts_author'] = ts_author

        # Output time series. Examples:
        # incomePerDay_exxon, macbook, (output, Exxon_4)
        # incomePerDay_goodyear, macbook, (output, Goodyear)
        # gasoline_exxon, macbook, (output, Exxon_4)
        if re.search('\(output,.*\)$', name):
            name_wo_braces = re.sub(r'[()]', '', name)
            attrs = name_wo_braces.split(',')
            (ts_name, ts_author, _, model_name), rest = attrs[:4], attrs[4:]
            ts['result_type'] = 'Output time series'
            ts['ts_name'] = ts_name
            ts['ts_author'] = ts_author
            ts['model_name'] = model_name

        # Intermediate input time series. Examples:
        # gasoline_exxon, Goodyear, macbook, input, source_type: output, Exxon_4, gasoline_exxon, macbook
        # Income_tax_rate, Exxon_4, macbook, input, source_type: timeseries, Income_tax_rate, macbook
        # G & A_Exxon, Exxon_4, macbook, input, source_type: timeseries, G & A_Exxon, macbook
        # oil, Goodyear, macbook, input, source_type: timeseries, oil, macbook
        # oil, Exxon_4, macbook, input, source_type: timeseries, oil, macbook
        if re.search('input,source_type:', name):
            attrs = name.split(',')
            (ts_name, model_name, ts_author, _), source = attrs[:4], attrs[4:]
            ts['result_type'] = 'Intermediate input time series'
            ts['ts_name'] = ts_name
            ts['ts_author'] = ts_author
            ts['model_name'] = model_name
            if re.search('input,source_type:output', name):
                source_model_name, rest = source[1], source[2:]
                ts['source_model_name'] = source_model_name
                ts['source_type'] = 'model'
            else:
                ts['source_type'] = 'timeseries'

        time_series.append(ts)

    time_series.sort(key=lambda ts_item: ts_item['result_type'], reverse=False)

    return render_template('results.html', results=results, time_series=time_series)


# TODO: figure out proper validation
class NoValidationSelectField(SelectField):
    def pre_validate(self, form):
        """per_validation is disabled"""


class ChangeOneModelForm(FlaskForm):
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(ChangeOneModelForm, self).__init__(csrf_enabled=csrf_enabled, *args, **kwargs)

    model_system_name = NoValidationSelectField('Model', [validators.required()], choices=[])
    input_source_initial = NoValidationSelectField('Initial input', [validators.required()], choices=[])
    input_source_final = NoValidationSelectField('Final input', [validators.required()], choices=[])


class ChangeAllModelsForm(FlaskForm):
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(ChangeAllModelsForm, self).__init__(csrf_enabled=csrf_enabled, *args, **kwargs)

    input_source_initial = NoValidationSelectField('Initial input', [validators.required()], choices=[])
    input_source_final = NoValidationSelectField('Final input', [validators.required()], choices=[])


class ChangeInputNewValue(FlaskForm):
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(ChangeInputNewValue, self).__init__(csrf_enabled=csrf_enabled, *args, **kwargs)

    input_source_initial = NoValidationSelectField('Initial input', [validators.required()], choices=[])
    start_day = DateField('Start day', [validators.required()], '%Y-%m-%d', default=datetime.today())
    number_of_days = IntegerField('Number of days', [validators.required()])
    new_value = FloatField('Delta', [validators.required()])


class ChangeInputAddDelta(FlaskForm):
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(ChangeInputAddDelta, self).__init__(csrf_enabled=csrf_enabled, *args, **kwargs)

    input_source_initial = NoValidationSelectField('Initial input', [validators.required()], choices=[])
    start_day = DateField('Start day', [validators.required()], '%Y-%m-%d', default=datetime.today())
    number_of_days = IntegerField('Number of days', [validators.required()])
    delta = FloatField('New Value', [validators.required()])


class RunForm(FlaskForm):
    start_day = DateField('Start day', [validators.required()], '%Y-%m-%d', default=datetime.today())
    number_of_days = IntegerField('Number of days', [validators.required()])
    exe_models = SelectMultipleField('Execute models', [validators.required()])
    change_input_series_one_model = FieldList(FormField(ChangeOneModelForm), min_entries=0)
    change_input_series_all_models = FieldList(FormField(ChangeAllModelsForm), min_entries=0)
    change_timeseries_value_several_days = FieldList(FormField(ChangeInputNewValue), min_entries=0)
    change_timeseries_value_several_days_add_delta = FieldList(FormField(ChangeInputAddDelta), min_entries=0)


def get_models_choices():
    models = load_json('models.json')
    return [
        (model['model_system_name'], model['model_name_user'] + ':' + model['author'])
        for model in models
    ]


def get_inputs_choices_by_model(name):
    models = load_json('models.json')
    model = next(item for item in models if item['model_system_name'] == name)
    return [(
        value['series_name_system'],
        value['series_name_system'] + ':' + value['series_name_user']
    ) for key, value in model['inputs'].iteritems()]


def get_inputs_choices():
    models = load_json('models.json')
    inputs_by_models = [get_inputs_choices_by_model(model['model_system_name']) for model in models]
    return [item for inputs in inputs_by_models for item in inputs]


# returns list of commands of form data
def get_commands(form):
    result = []
    for field in form:
        if field.name == 'start_day':
            result.append({'command': field.name, 'start_day': str(field.data)})
        elif field.name == 'number_of_days':
            result.append({'command': field.name, 'number_of_days': field.data})
        elif field.name == 'exe_models':
            result.append({'command': field.name, 'include': field.data})
        elif field.name == 'change_input_series_one_model':
            for entry in field.entries:
                result.append({
                    'command': field.name,
                    'model_system_name': entry.model_system_name.data,
                    'input_source_initial': entry.input_source_initial.data,
                    'input_source_final': entry.input_source_final.data
                })
        elif field.name == 'change_input_series_all_models':
            for entry in field.entries:
                result.append({
                    'command': field.name,
                    'input_source_initial': entry.input_source_initial.data,
                    'input_source_final': entry.input_source_final.data
                })
        elif field.name == 'change_timeseries_value_several_days':
            for entry in field.entries:
                result.append({
                    'command': field.name,
                    'input_source_initial': entry.input_source_initial.data,
                    'start_day': str(entry.start_day.data),
                    'number_of_days': entry.number_of_days.data,
                    'new_value': entry.new_value.data
                })
        elif field.name == 'change_timeseries_value_several_days_add_delta':
            for entry in field.entries:
                result.append({
                    'command': field.name,
                    'input_source_initial': entry.input_source_initial.data,
                    'start_day': str(entry.start_day.data),
                    'number_of_days': entry.number_of_days.data,
                    'delta': entry.delta.data
                })

    return result


# creates flask form using data from request.data if any
def get_run_form():
    run_form = RunForm()
    # dynamically fill list or select options for available models
    run_form.exe_models.choices = get_models_choices()
    return run_form


# updates form with defaults from given commands
def set_form_defaults(form, commands):
    def get_command(command_name):
        return [item for item in commands if item['command'] == command_name]

    def str_to_datetime(str):
        if not str or str == 'None':
            str = datetime.today().strftime('%Y-%m-%d')
        str = str[:10]
        return datetime.strptime(str, '%Y-%m-%d')

    # set default values for single fields
    if get_command('start_day'):
        form.start_day.data = str_to_datetime(get_command('start_day')[0]['start_day'])
    if get_command('number_of_days'):
        form.number_of_days.data = get_command('number_of_days')[0]['number_of_days']
    if get_command('exe_models'):
        form.exe_models.data = get_command('exe_models')[0]['include']

    # set default values for compound fields
    # TODO: avoid ifs, use if request.get instead
    if not form.change_input_series_one_model:
        for command in get_command('change_input_series_one_model'):
            form.change_input_series_one_model.append_entry()
    if not form.change_input_series_all_models:
        for command in get_command('change_input_series_all_models'):
            form.change_input_series_all_models.append_entry()
    if not form.change_timeseries_value_several_days:
        for command in get_command('change_timeseries_value_several_days'):
            form.change_timeseries_value_several_days.append_entry()
    if not form.change_timeseries_value_several_days_add_delta:
        for command in get_command('change_timeseries_value_several_days_add_delta'):
            form.change_timeseries_value_several_days_add_delta.append_entry()

    for index, command in enumerate(get_command('change_input_series_one_model')):
        sub_form = form.change_input_series_one_model[index]
        sub_form.model_system_name.choices = get_models_choices()
        sub_form.model_system_name.data = command.get('model_system_name', '')
        sub_form.input_source_initial.choices = get_inputs_choices()
        sub_form.input_source_initial.data = command.get('input_source_initial', '')
        sub_form.input_source_final.choices = get_inputs_choices()
        sub_form.input_source_final.data = command.get('input_source_final', '')
    for index, command in enumerate(get_command('change_input_series_all_models')):
        sub_form = form.change_input_series_all_models[index]
        sub_form.input_source_initial.choices = get_inputs_choices()
        sub_form.input_source_initial.data = command.get('input_source_initial', '')
        sub_form.input_source_final.choices = get_inputs_choices()
        sub_form.input_source_final.data = command.get('input_source_final', '')
    for index, command in enumerate(get_command('change_timeseries_value_several_days')):
        sub_form = form.change_timeseries_value_several_days[index]
        sub_form.input_source_initial.choices = get_inputs_choices()
        sub_form.input_source_initial.data = command.get('input_source_initial', '')
        sub_form.start_day.data = str_to_datetime(command.get('start_day', ''))
        sub_form.number_of_days.data = command.get('number_of_days', '')
        sub_form.new_value.data = command.get('new_value', '')
    for index, command in enumerate(get_command('change_timeseries_value_several_days_add_delta')):
        sub_form = form.change_timeseries_value_several_days_add_delta[index]
        sub_form.input_source_initial.choices = get_inputs_choices()
        sub_form.input_source_initial.data = command.get('input_source_initial', '')
        sub_form.start_day.data = str_to_datetime(command.get('start_day', ''))
        sub_form.number_of_days.data = command.get('number_of_days', '')
        sub_form.delta.data = command.get('delta', '')


@app.route('/run')
def view_run():
    return render_template('run.html')


@app.route('/run/form/init', methods=['POST'])
def view_run_init():
    run_form = get_run_form()
    commands = json.loads(request.data)['commands']
    set_form_defaults(run_form, commands)

    return render_template('run_form.html', form=run_form)


@app.route('/run/form/submit', methods=['POST'])
def view_run_submit():
    run_form = get_run_form()

    if run_form.validate_on_submit():
        commands = get_commands(run_form)
        # TODO: run modeling with commands
        commands_string = json.dumps(commands, sort_keys=True, indent=4)
        return render_template('run_success.html', commands=commands_string)

    commands = get_commands(run_form)
    set_form_defaults(run_form, commands)

    return render_template('run_form.html', form=run_form)


@app.route('/run/form/add/<field>', methods=['POST'])
def view_run_add(field):
    run_form = get_run_form()
    run_form[field].append_entry()
    commands = get_commands(run_form)
    set_form_defaults(run_form, commands)

    return render_template('run_form.html', form=run_form)


@app.route('/run/form/remove/<field>', methods=['POST'])
def view_run_remove(field):
    run_form = get_run_form()
    run_form[field].pop_entry()
    commands = get_commands(run_form)
    set_form_defaults(run_form, commands)

    return render_template('run_form.html', form=run_form)


if __name__ == '__main__':
    app.run()
