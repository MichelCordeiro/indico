<div class="groupTitle"> ${ _("Instance Tracking settings") }</div>

<form id="it-form" action="${ postURL }" method="POST">
    <input id="hidden-button-pressed" type="hidden" name="button-pressed">

    <div>
        <div class="instance-tracking-settings">
            <div class="clearfix">
                <div class="field-label">
                    <label class="dataCaptionFormat status-label">${ _('Status') }</label>
                </div>
                <div class="field-input">
                    <input class="hidden-input" id="enable" type="checkbox" name="enable" value="1" ${ checked }>
                    <div class="toggle-button">
                        <div class="toggle"></div>
                    </div>
                </div>
            </div>
            <div class="clearfix">
                <div class="field-label">
                    <label class="dataCaptionFormat" for="contact">${ _("Contact person name") }</label>
                </div>
                <div class="field-input">
                    <input id="contact" type="text" name="contact" value="${ contact }" disabled>
                </div>
            </div>
            <div class="clearfix">
                <div class="field-label">
                    <label class="dataCaptionFormat" for="email">${ _("Contact email address") }</label>
                </div>
                <div class="field-input">
                    <input id="email" type="text" name="email" value="${ email }" disabled>
                </div>
            </div>
            <div class="clearfix">
                <div class="group">
                    <a id="button-save" class="i-button disabled">Save</a>
                    <a id="button-cancel" class="i-button disabled">Cancel</a>
                </div>
            </div>
        </div>
        <div class="i-box titled out-of-sync">
            <div class="i-box-header">
                <div class="i-box-title">Data out of sync!</div>
            </div>
            <div class="i-box-content">
                <div class="missing-record-text">
                    <div>It seems like we lost your information on our server.</div>
                    <div>Click <strong>update</strong> to send them again.</div>
                </div>
                <div class="out-of-sync-text">
                    <div>It seems like you changed some information lately.</div>
                    <div>The information out of sync are:</div>
                    <ul>
                        <li id="out-of-sync-url">URL</li>
                        <li id="out-of-sync-contact">Contact name</li>
                        <li id="out-of-sync-email">Email</li>
                        <li id="out-of-sync-organisation">Organisation</li>
                    </ul>
                    <div>Click <strong>update</strong> to send them again.</div>
                </div>
                <input id="hidden-update-type" type="hidden" name="update-it-type" value="none">
                <div class="group">
                    <a id="button-update" class="i-button">Update</a>
                </div>
            </div>
        </div>
    </div>

</form>

<script type="text/javascript">

    $('.toggle-button').on('click', function() {
        var $this = $(this);
        $this.toggleClass('toggled');
        var toggled = $this.hasClass('toggled');
        var checkbox = $('#enable');
        var contact = $('#contact');
        var email = $('#email');
        checkbox.prop('checked', toggled);
        contact.prop('disabled', !toggled);
        email.prop('disabled', !toggled);
        $('.group a').removeClass('disabled');
    });
    if ($('#enable').prop('checked')) {
        $('.toggle-button').toggleClass('toggled');
        var contact = $('#contact');
        var email = $('#email');
        contact.prop('disabled', false);
        email.prop('disabled', false);
    }
    $('input').on('input', function(){
        $('.group a').removeClass('disabled');
    });

    var hiddenUpdate = $('#hidden-update-type');
    var outOfSync = $(".out-of-sync");
    if (${ itEnabled }) {
        $.ajax({
            url: "${ updateURL }${ uuid }",
            type: "GET",
            dataType: "json",
            success: function(response){
                var url = ${ url | n,j };
                var contact = ${ contact | n,j };
                var email = ${ email | n,j };
                var organisation = ${ organisation | n,j };

                var ok = true;
                if (url != response.url) {
                    $('#out-of-sync-url').show();
                    ok = false;
                }
                if (contact != response.contact) {
                    $('#out-of-sync-contact').show();
                    ok = false;
                }
                if (email != response.email) {
                    $('#out-of-sync-email').show();
                    ok = false;
                }
                if (organisation != response.organisation) {
                    $('#out-of-sync-organisation').show();
                    ok = false;
                }

                if (!ok) {
                    hiddenUpdate.val("update");
                    $('.out-of-sync-text').show();
                    outOfSync.show();
                }
            },
            error: function(){
                hiddenUpdate.val("register");
                $('.missing-record-text').show();
                outOfSync.show();
            }
        });
    }

    var hiddenButtonPressed = $('#hidden-button-pressed');
    var itForm = $('#it-form');
    $('#button-save').on('click', function(){
        if (! $(this).hasClass('disabled')) {
            hiddenButtonPressed.val('save');
            itForm.submit();
        }
    });
    $('#button-cancel').on('click', function(){
        if (! $(this).hasClass('disabled')) {
            hiddenButtonPressed.val('cancel');
            itForm.submit();
        }
    });
    $('#button-update').on('click', function(){
        if (! $(this).hasClass('disabled')) {
            hiddenButtonPressed.val('update');
            itForm.submit();
        }
    });

</script>