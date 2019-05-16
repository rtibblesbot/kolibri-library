// This gets sourced as the last tag in <head>

window._localStorage = {};  // used as backedn for getStoredValue/setStoredValue
 
Modernizr.touch = true;    // needed to force mobile layout and show nav buttons

window.story = {};

setStoredValue('diffRange', 'All');          // Set the age range to avoid popup

$(document).ready(function() {
  $('#maincontent').show();
  animateButtons(0.9);            // This is necessary to force-show the buttons
});
