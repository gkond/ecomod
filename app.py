from flask import Flask, render_template
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms import IntegerField, FloatField, DateField, SelectField, \
    SelectMultipleField, FieldList, FormField, validators
from datetime import datetime
import os.path
import json
import re

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

    model = NoValidationSelectField('Model', [validators.required()], choices=[])
    input_initial = NoValidationSelectField('Initial input', [validators.required()], choices=[])
    input_final = NoValidationSelectField('Final input', [validators.required()], choices=[])


class ChangeAllModelsForm(FlaskForm):
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(ChangeAllModelsForm, self).__init__(csrf_enabled=csrf_enabled, *args, **kwargs)

    input_initial = NoValidationSelectField('Initial input', [validators.required()], choices=[])
    input_final = NoValidationSelectField('Final input', [validators.required()], choices=[])


class ChangeInputNewValue(FlaskForm):
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(ChangeInputNewValue, self).__init__(csrf_enabled=csrf_enabled, *args, **kwargs)

    input_initial = NoValidationSelectField('Initial input', [validators.required()], choices=[])
    start_day = DateField('Start day', [validators.required()], '%Y-%m-%d')
    number_of_days = IntegerField('Number of days', [validators.required()])
    new_value = FloatField('Delta', [validators.required()])


class ChangeInputAddDelta(FlaskForm):
    def __init__(self, csrf_enabled=False, *args, **kwargs):
        super(ChangeInputAddDelta, self).__init__(csrf_enabled=csrf_enabled, *args, **kwargs)

    input_initial = NoValidationSelectField('Initial input', [validators.required()], choices=[])
    start_day = DateField('Start day', [validators.required()], '%Y-%m-%d')
    number_of_days = IntegerField('Number of days', [validators.required()])
    delta = FloatField('New Value', [validators.required()])


class RunForm(FlaskForm):
    start_day = DateField('Start day', [validators.required()], '%Y-%m-%d')
    number_of_days = IntegerField('Number of days', [validators.required()])
    exe_models = SelectMultipleField('Execute models', [validators.required()])
    change_input_series_one_model = FieldList(FormField(ChangeOneModelForm), min_entries=0)
    change_input_series_all_models = FieldList(FormField(ChangeAllModelsForm), min_entries=0)
    change_timeseries_value_several_days = FieldList(FormField(ChangeInputNewValue), min_entries=0)
    change_timeseries_value_several_days_add_delta = FieldList(FormField(ChangeInputAddDelta), min_entries=0)


@app.route('/run', methods=['GET', 'POST'])
def view_run():
    models = load_json('models.json')

    def get_models_choices():
        return [
            (model['model_system_name'], model['model_name_user'] + ':' + model['author'])
            for model in models
        ]

    def get_inputs_choices_by_model(name):
        model = next(item for item in models if item['model_system_name'] == name)
        return [(
            value['series_name_system'],
            value['series_name_system'] + ':' + value['series_name_user']
        ) for key, value in model['inputs'].iteritems()]

    def get_inputs_choices():
        inputs_by_models = [get_inputs_choices_by_model(model['model_system_name']) for model in models]
        return [item for inputs in inputs_by_models for item in inputs]

    run_form = RunForm()
    run_form.exe_models.choices = get_models_choices()

    if run_form.validate_on_submit():
        def get_commands():
            result = []
            for field in run_form:
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
                            'model': entry.model.data,
                            'input_initial': entry.input_initial.data,
                            'input_final': entry.input_final.data
                        })
                elif field.name == 'change_input_series_all_models':
                    for entry in field.entries:
                        result.append({
                            'command': field.name,
                            'input_initial': entry.input_initial.data,
                            'input_final': entry.input_final.data
                        })
                elif field.name == 'change_timeseries_value_several_days':
                    for entry in field.entries:
                        result.append({
                            'command': field.name,
                            'input_initial': entry.input_initial.data,
                            'start_day': str(entry.start_day.data),
                            'number_of_days': entry.number_of_days.data,
                            'new_value': entry.new_value.data
                        })
                elif field.name == 'change_timeseries_value_several_days_add_delta':
                    for entry in field.entries:
                        result.append({
                            'command': field.name,
                            'input_initial': entry.input_initial.data,
                            'start_day': str(entry.start_day.data),
                            'number_of_days': entry.number_of_days.data,
                            'delta': entry.delta.data
                        })

            return result

        commands = get_commands(run_form)
        # TODO: run modeling with commands

        return render_template('run_success.html', commands=json.dumps(commands, sort_keys=True, indent=4))

    # get default values
    default_state = load_json('run.json')

    def get_state_value(command_name):
        return [item for item in default_state if item['command'] == command_name]

    # set default values for single fields
    run_form.start_day.data = datetime.strptime(get_state_value('start_day')[0]['start_day'], '%Y-%m-%d')
    run_form.number_of_days.data = get_state_value('number_of_days')[0]['number_of_days']
    run_form.exe_models.data = get_state_value('exe_models')[0]['include']

    # set default values for compound fields
    if not run_form.change_input_series_one_model:
        for command in get_state_value('change_input_series_one_model'):
            run_form.change_input_series_one_model.append_entry()
    if not run_form.change_input_series_all_models:
        for command in get_state_value('change_input_series_all_models'):
            run_form.change_input_series_all_models.append_entry()
    if not run_form.change_timeseries_value_several_days:
        for command in get_state_value('change_timeseries_value_several_days'):
            run_form.change_timeseries_value_several_days.append_entry()
    if not run_form.change_timeseries_value_several_days_add_delta:
        for command in get_state_value('change_timeseries_value_several_days_add_delta'):
            run_form.change_timeseries_value_several_days_add_delta.append_entry()

    for index, command in enumerate(get_state_value('change_input_series_one_model')):
        sub_form = run_form.change_input_series_one_model[index]
        sub_form.model.choices = get_models_choices()
        sub_form.model.data = command['model_system_name']
        sub_form.input_initial.choices = get_inputs_choices()
        sub_form.input_initial.data = command['input_source_initial']
        sub_form.input_final.choices = get_inputs_choices()
        sub_form.input_final.data = command['input_source_final']
    for index, command in enumerate(get_state_value('change_input_series_all_models')):
        sub_form = run_form.change_input_series_all_models[index]
        sub_form.input_initial.choices = get_inputs_choices()
        sub_form.input_initial.data = command['input_source_initial']
        sub_form.input_final.choices = get_inputs_choices()
        sub_form.input_final.data = command['input_source_final']
    for index, command in enumerate(get_state_value('change_timeseries_value_several_days')):
        sub_form = run_form.change_timeseries_value_several_days[index]
        sub_form.input_initial.choices = get_inputs_choices()
        sub_form.input_initial.data = command['input_source_initial']
        sub_form.start_day.data = datetime.strptime(command['start_day'], '%Y-%m-%d')
        sub_form.number_of_days.data = command['number_of_days']
        sub_form.new_value.data = command['new_value']
    for index, command in enumerate(get_state_value('change_timeseries_value_several_days_add_delta')):
        sub_form = run_form.change_timeseries_value_several_days_add_delta[index]
        sub_form.input_initial.choices = get_inputs_choices()
        sub_form.input_initial.data = command['input_source_initial']
        sub_form.start_day.data = datetime.strptime(command['start_day'], '%Y-%m-%d')
        sub_form.number_of_days.data = command['number_of_days']
        sub_form.delta.data = command['delta']

    return render_template('run.html', form=run_form)


if __name__ == '__main__':
    app.run()
