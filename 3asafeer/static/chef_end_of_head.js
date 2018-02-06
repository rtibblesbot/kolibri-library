// This gets sourced as the last tag in <head>

window._localStorage = {};
Modernizr.touch = true;
window.story = {};

$(document).ready(function() {
  $('#maincontent').show();
  animateButtons(0.9);
});
