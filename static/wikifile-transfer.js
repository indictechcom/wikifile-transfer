$(document).ready(function () {

    /*
     * Detect the Changes on the Input Textfeild
     */
    $('#srcUrl').on('input propertychange paste', function () {

        if ($('#srcUrl').val() !== "") {
            let src_url_str = $('#srcUrl').val();

            try {
                var src_url = new URL(src_url_str),
                    src_filename = src_url.href.split('/').slice(-1),
                    src_host = src_url.host;

                srcImageVal(src_host, src_filename);
            } catch {
                $('#srcUrl').removeClass('is-valid').addClass('is-invalid');
            }
        } else {
            $('#srcUrl').removeClass('is-valid').removeClass('is-invalid');
        }
    });

    // Check whether the host and image name is correct or not
    async function srcImageVal(src_host, file) {
        let src_endpoint = 'https://' + src_host + '/w/api.php',
            params = {
                action: "query",
                format: "json",
                prop: "imageinfo",
                titles: file,
                iilocalonly: "1",
                iiprop: "url"
            };

        src_endpoint = src_endpoint + '?origin=*';
        Object.keys(params).forEach(function (key) {
            src_endpoint += "&" + key + "=" + params[key];
        });

        fetch(src_endpoint)
            .then(function (response) {
                return response.json();
            })
            .then(function (response) {
                var pages = response.query.pages;
                try {
                    var image_url = pages[Object.keys(pages)[0]].imageinfo[0].url;
                    $('#srcUrl').removeClass('is-invalid').addClass('is-valid');
                    $('#tr-filename').val($('#srcUrl').val().split('/').slice(-1)[0].split(':')[1].replace(/\.[^/.]+$/, ""));
                    trNameVal();
                    changeBtnStatus();

                } catch {
                    $('#srcUrl').removeClass('is-valid').addClass('is-invalid');
                }
            })
            .catch(function (error) {
                $('#srcUrl').removeClass('is-valid').addClass('is-invalid');
            });
    }

    /*
     * Validation work on the Target project and language
     */
    $('#tr-lang').addClass('is-valid');

    $('#tr-lang').change(function () {
        targetVal();
        if ($('#tr-filename').val() !== "") {
            trNameVal();
        }
    });

    $('#tr-project').change(function () {
        targetVal();
        if ($('#tr-filename').val() !== "") {
            trNameVal();
        }
    });

    // Target Validation
    function targetVal() {
        var tr_lang = $("#tr-lang").find("option:selected").attr('value'),
            tr_project = $("#tr-project").find("option:selected").attr('value');

        $.get('https://' + tr_lang + '.' + tr_project + '.org/w/api.php', {origin: "*"}).done(function () {
            $('#tr-lang').removeClass('is-invalid').addClass('is-valid');
            changeBtnStatus();
        }).fail(function () {
            $('#tr-lang').removeClass('is-valid').addClass('is-invalid');
        });
    }

    /*
     * Target File name validation
     */
    $('#tr-filename').on('input propertychange paste', function () {
        trNameVal();
    });

    function trNameVal() {
        if( $('#tr-filename').val() !== ''){
            var tr_lang = $("#tr-lang").find("option:selected").attr('value'),
                tr_project = $("#tr-project").find("option:selected").attr('value'),
                tr_filename = $('#tr-filename').val(),
                tr_fileextn = $('#srcUrl').val().split('/').slice(-1)[0].split('.').slice(-1);

            var param = {
                "action": "query",
                "format": "json",
                "prop": "imageinfo",
                "titles": "File:" + tr_filename + "." + tr_fileextn,
                "iilocalonly": 1,
                "origin": "*"
            };

            $.get('https://' + tr_lang + '.' + tr_project + '.org/w/api.php', param).done(function (res) {
                if (res.query.pages["-1"]) {
                    $('#trfilename-error-hint').hide();
                    $('#tr-filename').removeClass('is-invalid').addClass('is-valid');
                    changeBtnStatus();
                } else {
                    $('#tr-filename').removeClass('is-valid').addClass('is-invalid');
                    $('#trfilename-error-hint').show().text('Another file exist with this name');
                    changeBtnStatus();
                }
            }).fail(function () {
                $('#tr-filename').removeClass('is-valid').addClass('is-invalid');
            });
        } else{
            $('#tr-filename').removeClass('is-valid').removeClass('is-invalid');
        }
    }

    function changeBtnStatus(){
        if ( $('#srcUrl').hasClass("is-valid") && $('#tr-lang').hasClass("is-valid") && $('#tr-filename').hasClass("is-valid") ) {
            $('#wt-submit').prop("disabled", false);
        } else {
            $('#wt-submit').prop("disabled", true);
        }
    }
});