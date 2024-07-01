(function() {

var localStorage = {}, sessionStorage = {};
try { localStorage = window.localStorage; } catch (e) { }
try { sessionStorage = window.sessionStorage; } catch (e) { }

// Kludge: This isn't a clean way to do it. But it works for now.
// It doesn't take into account collapsed state change that happen when expandTo
// is called. User must click the un-collapse arrow for that.
// This also relies on this file being loaded after full_list.js so that the
// original YARD enableToggles function is called before this one.
function persistentToggles() {
  // Remember the collapsed state when toggling the first two levels.
  $('#full_list a.toggle').on('click', function(evt) {
    console.log('persistentToggles');
    var $item = $(this).parent().parent();
    var key = $item.attr('id');
    var value = $item.hasClass('collapsed');
    localStorage.setItem(key, value);
  });
  // Load initial state.
  $('#full_list a.toggle').each(function() {
    var $item = $(this).parent().parent();
    var key = $item.attr('id');
    var value = localStorage.getItem(key);
    if (value === 'true') {
      $item.addClass('collapsed');
    }
  });
}

$(document).ready(function() {
  console.log('READY: sketchup.js');
  persistentToggles();
});

})();
