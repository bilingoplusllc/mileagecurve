"""
Поиск по каталогу. Индекс строится на сборке, поиск работает в браузере.

Зачем: человек приходит за «моим Ford Escape 2013». Сейчас ему предлагают
318 чипов по алфавиту, начиная с Acura MDX. Это главный провал продукта,
и оформлением он не лечится.

Правила:
  - ванильный JS, ноль зависимостей, ноль внешних запросов (D-009);
  - индекс маленький: 318 записей ≈ 25 КБ, грузится один раз и кэшируется;
  - БЕЗ JS страница остаётся полностью рабочей — под формой лежит обычный
    список марок со ссылками, а форма имеет action на страницу «все марки».
"""
from __future__ import annotations

import json
import re

import names


def build_index(pages: list[dict]) -> str:
    """Компактный индекс: [марка, модель, год_от, год_до, url, жалоб]."""
    rows = []
    for p in sorted(pages, key=lambda x: -x["n"]):
        rows.append([names.display(p["make"]), names.display(p["model"]),
                     p["y0"], p["y1"], p["url"], p["n"]])
    return json.dumps(rows, separators=(",", ":"), ensure_ascii=False)


SEARCH_JS = r"""
(function () {
  var box = document.getElementById('q');
  if (!box) return;
  var out = document.getElementById('qr');
  var form = document.getElementById('qf');
  var idx = null, loading = false, lastQuery = '', active = -1;

  // The index loads on first focus, not on page load: most visits arrive from
  // search directly on a generation page and never touch this box.
  function load(cb) {
    if (idx) { cb(); return; }
    if (loading) return;
    loading = true;
    var x = new XMLHttpRequest();
    x.open('GET', '/search-index.json', true);
    x.onload = function () {
      try { idx = JSON.parse(x.responseText); } catch (e) { idx = []; }
      loading = false; cb();
    };
    x.onerror = function () { loading = false; };
    x.send();
  }

  function norm(s) { return s.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim(); }

  function score(row, terms, year) {
    // row = [make, model, y0, y1, url, n]
    var hay = norm(row[0] + ' ' + row[1]);
    var words = hay.split(' ');
    var s = 0;
    for (var i = 0; i < terms.length; i++) {
      var t = terms[i], hit = 0;
      for (var j = 0; j < words.length; j++) {
        if (words[j] === t) { hit = 12; break; }              // whole word
        if (words[j].indexOf(t) === 0) { hit = Math.max(hit, 7); }  // prefix
        else if (words[j].indexOf(t) > 0) { hit = Math.max(hit, 3); }
      }
      if (!hit) return 0;                                     // every term must match
      s += hit;
    }
    if (year) {
      if (year >= row[2] && year <= row[3]) s += 25;           // year falls inside the generation
      else s -= Math.min(12, Math.abs(year < row[2] ? row[2] - year : year - row[3]));
    }
    return s + Math.min(row[5] / 900, 4);                      // nudge up where data is deeper
  }

  function render(list, q) {
    if (!q) { out.innerHTML = ''; out.hidden = true; active = -1; return; }
    if (!list.length) {
      out.innerHTML = '<p class="qr-none">Nothing matches “' + esc(q) + '”. ' +
        'Try just the model name, or <a href="/">browse by make</a>.</p>';
      out.hidden = false; return;
    }
    var h = '<ul class="qr-list" role="listbox">';
    for (var i = 0; i < list.length; i++) {
      var r = list[i];
      h += '<li role="option"><a href="' + r[4] + '"><span class="qr-car">' +
           esc(r[0] + ' ' + r[1]) + '</span> <span class="qr-yr">' + r[2] + '–' + r[3] +
           '</span><span class="qr-n">' + r[5].toLocaleString() + ' with mileage</span></a></li>';
    }
    out.innerHTML = h + '</ul>';
    out.hidden = false; active = -1;
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function run() {
    var q = box.value.trim();
    if (q === lastQuery) return;
    lastQuery = q;
    if (!q) { render([], ''); return; }
    load(function () {
      if (!idx) return;
      var ym = q.match(/\b(19|20)\d{2}\b/);
      var year = ym ? parseInt(ym[0], 10) : 0;
      var terms = norm(q.replace(/\b(19|20)\d{2}\b/, '')).split(' ').filter(Boolean);
      var hits = [];
      if (terms.length) {
        for (var i = 0; i < idx.length; i++) {
          var sc = score(idx[i], terms, year);
          if (sc > 0) hits.push([sc, idx[i]]);
        }
      } else if (year) {
        for (var k = 0; k < idx.length; k++) {
          if (year >= idx[k][2] && year <= idx[k][3]) hits.push([idx[k][5], idx[k]]);
        }
      }
      hits.sort(function (a, b) { return b[0] - a[0]; });
      render(hits.slice(0, 8).map(function (h) { return h[1]; }), q);
    });
  }

  box.addEventListener('focus', function () { load(function () {}); });
  box.addEventListener('input', run);
  box.addEventListener('keydown', function (e) {
    var items = out.querySelectorAll('.qr-list a');
    if (e.key === 'ArrowDown' && items.length) {
      e.preventDefault(); active = Math.min(active + 1, items.length - 1); items[active].focus();
    } else if (e.key === 'Escape') { box.value = ''; render([], ''); }
  });
  out.addEventListener('keydown', function (e) {
    var items = out.querySelectorAll('.qr-list a');
    if (!items.length) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); active = Math.min(active + 1, items.length - 1); items[active].focus(); }
    if (e.key === 'ArrowUp') {
      e.preventDefault(); active -= 1;
      if (active < 0) { active = -1; box.focus(); } else { items[active].focus(); }
    }
    if (e.key === 'Escape') { box.focus(); render([], ''); }
  });
  // Without JS the form goes to the make list; with JS, submit opens the top hit.
  form.addEventListener('submit', function (e) {
    var first = out.querySelector('.qr-list a');
    if (first) { e.preventDefault(); window.location = first.getAttribute('href'); }
  });
})();
"""


def search_markup() -> str:
    """Форма поиска. Работает и без JS: action ведёт на полный список."""
    return (
        '<form class="qbox" id="qf" action="/" method="get" role="search">'
        '<label class="vh" for="q">Find a vehicle</label>'
        '<input id="q" name="q" type="search" autocomplete="off" spellcheck="false" '
        'placeholder="Try “2013 Escape” or “Prius”" aria-describedby="qh">'
        '<button type="submit">Find</button>'
        '</form>'
        '<div id="qr" class="qr" hidden></div>'
        '<p class="qhint" id="qh">318 generations · type a model, or a year and a model</p>'
    )
