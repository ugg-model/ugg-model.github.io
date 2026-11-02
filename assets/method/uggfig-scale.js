/* The method figure is authored on a fixed 1280x560 grid so its proportions match
   the paper exactly. Scale it to whatever width the column gives us. */
(function () {
  var W = 1280, H = 560;
  function fit() {
    document.querySelectorAll('.uggfig').forEach(function (box) {
      var stage = box.querySelector('.uggfig-stage');
      if (!stage) return;
      var s = Math.min(1, box.clientWidth / W);
      stage.style.transform = 'scale(' + s + ')';
      box.style.height = (H * s) + 'px';
    });
  }
  fit();
  addEventListener('resize', fit);
  addEventListener('load', fit);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(fit);
})();
