from flask import Flask, render_template, request, jsonify
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms import IntegerField, DateField, SelectMultipleField, validators
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
def home():
    return render_template('home.html')


@app.route('/models')
def all_models():
    models = load_json('models.json')
    return render_template('models.html', models=models)


@app.route('/results')
def results():
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

    time_series.sort(key=lambda ts: ts['result_type'], reverse=False)

    return render_template('results.html', results=results, time_series=time_series)


class RunForm(FlaskForm):
    start_day = DateField('Start day', format='%Y-%m-%d')
    number_of_days = IntegerField('Number of days')
    exe_models = SelectMultipleField('Execute models', choices=[])
    change_one_model = FieldList(FormField(ChangeOneModelForm), min_entries=0)
    change_all_models = FieldList(FormField(ChangeAllModelsForm), min_entries=0)
    change_input_value_new = FieldList(FormField(ChangeInputValueNew), min_entries=0)
    change_input_value_delta = FieldList(FormField(ChangeInputValueDelta), min_entries=0)



@app.route('/run', methods=['GET', 'POST'])
def run():
    models = load_json('models.json')
    state = load_json('run.json')

    def getCommand(command):
        return [item for item in state if item['command'] == command]

    def getModelsChoices():
        return [(
            model['model_system_name'],
            model['model_name_user'] + ':' + model['author']
        ) for model in models]

    def getInputsChoicesByModel(name):
        model = next(item for item in models if item['model_system_name'] == name)
        return [(
            value['series_name_system'],
            value['series_name_system'] + ':' + value['series_name_user']
        ) for key, value in model['inputs'].iteritems()]

    def getInputsChoices():
        list = [getInputsChoicesByModel(model['model_system_name']) for model in models]
        return [item for sublist in list for item in sublist]

    # if request.method == 'GET':
    form = RunForm()
    form.exe_models.choices = getModelsChoices()

    if form.validate_on_submit():
        return render_template('run_success.html', form=form)

    form.start_day.data = datetime.strptime(getCommand('start_day')[0]['start_day'], '%Y-%m-%d')
    form.number_of_days.data = getCommand('number_of_days')[0]['number_of_days']
    form.exe_models.data = getCommand('exe_models')[0]['include']

    for sub_form in form.change_one_model:
        sub_form.model.choices = getModelsChoices()
        sub_form.input_initial.choices = getInputsChoices()
        print(sub_form.input_initial.default)
        sub_form.input_initial.default = 'seires_6'
        print(sub_form.input_initial.default)
        sub_form.input_final.choices = getInputsChoices()

    for sub_form in form.change_all_models:
        sub_form.input_initial.choices = getInputsChoices()
        sub_form.input_final.choices = getInputsChoices()

    for sub_form in form.change_input_value_new:
        sub_form.input_initial.choices = getInputsChoices()

    for sub_form in form.change_input_value_delta:
        sub_form.input_initial.choices = getInputsChoices()

    return render_template('run2.html', form=form)


if __name__ == '__main__':
    app.run()
