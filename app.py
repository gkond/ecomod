from flask import Flask
from flask import render_template
import os.path
import json
import re

app = Flask(__name__)


@app.route('/')
def home():
    return 'Home page'


@app.route('/all-models')
def all_models():
    filename = os.path.join(app.static_folder, 'all-models.json')
    data = json.load(open(filename))
    return render_template('all-models.html', data=data)


@app.route('/all-results')
def results():
    filename = os.path.join(app.static_folder, 'all-results.json')
    resp = json.load(open(filename))

    time_series = []
    for name, values in resp.items():
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
            [ts_name, ts_author, *_] = map(str.strip, attrs)
            ts['result_type'] = 'Input time series'
            ts['ts_name'] = ts_name
            ts['ts_author'] = ts_author

        # Output time series. Examples:
        # incomePerDay_exxon, macbook, (output, Exxon_4)
        # incomePerDay_goodyear, macbook, (output, Goodyear)
        # gasoline_exxon, macbook, (output, Exxon_4)
        if re.search('\(output,.*\)$', name):
            attrs = [re.sub(r'[()]', '', attr) for attr in name.split(',')]
            [ts_name, ts_author, _, model_name, *_] = map(str.strip, attrs)
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
            ts_name, model_name, ts_author, _, *source = map(str.strip, attrs)
            ts['result_type'] = 'Intermediate input time series'
            ts['ts_name'] = ts_name
            ts['ts_author'] = ts_author
            ts['model_name'] = model_name
            if re.search('input,source_type:output', name):
                _, source_model_name, *_ = source
                ts['source_model_name'] = source_model_name
                ts['source_type'] = 'model'
            else:
                ts['source_type'] = 'timeseries'

        time_series.append(ts)

    time_series.sort(key=lambda ts: ts['result_type'], reverse=False)

    return render_template('all-results.html', results=results, time_series=time_series)


if __name__ == '__main__':
    app.run()
