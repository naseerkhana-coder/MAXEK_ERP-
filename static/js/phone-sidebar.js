/* On phones the shell's fixed 272px sidebar leaves ~100px for the page. Collapse it to the icon
 * rail for pages that include this script. The choice is not saved, so a desktop user's saved
 * sidebar preference is never changed. */
(function () {
  "use strict";
  var shell = document.querySelector("[data-pro-dash-shell]");
  if (shell && window.matchMedia && window.matchMedia("(max-width: 760px)").matches) {
    shell.classList.add("is-sidebar-collapsed");
  }
})();
