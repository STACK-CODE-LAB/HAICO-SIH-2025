document.getElementById('tabBar').addEventListener('click', function (e) {
  var btn = e.target.closest('.tab');
  if (!btn) return;

  document.querySelectorAll('.tab').forEach(function (t) {
    t.classList.remove('active');
  });
  document.querySelectorAll('.tab-pane').forEach(function (p) {
    p.classList.remove('active');
  });

  btn.classList.add('active');
  document.getElementById(btn.dataset.target).classList.add('active');
});