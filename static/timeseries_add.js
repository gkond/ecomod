$(function () {
    $('#ts_entity').on('change', function (e) {
        if (e.target.value == 'new') {
            $('#ts_entity_new_row').show();
        } else {
            $('#ts_entity_new_row').hide();
        }
    }).change()
    $('#ts_index').on('change', function (e) {
        if (e.target.value == 'new') {
            $('#ts_index_new_row').show();
        } else {
            $('#ts_index_new_row').hide();
        }
    }).change()
})
