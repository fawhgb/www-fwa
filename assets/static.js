/* Static search uses archived result markup; no fetch, API, or PHP is needed. */
(function () {
  'use strict';
  var root = window.FAW_STATIC_ROOT;
  function localLinks(scope) {
    scope.querySelectorAll('a[href],form[action]').forEach(function (el) {
      var attr = el.tagName === 'FORM' ? 'action' : 'href';
      var url = new URL(el.getAttribute(attr), root);
      if (url.hostname === 'www.faw.at' || url.hostname === 'faw.at') {
        el.setAttribute(attr, root + url.pathname.replace(/^\//, '').replace(/\/?$/, '/').replace(/^\//, '') + 'index.html' + url.search + url.hash);
      }
      if (el.tagName === 'FORM') el.action = root + 'index.html';
    });
  }
  document.querySelectorAll('form.search-form').forEach(function (form) { form.action = root + 'index.html'; });
  var params = new URLSearchParams(location.search);
  if (!params.has('s')) return;
  var query = params.get('s') || '';
  var feature = document.querySelector('#feature');
  if (feature) feature.remove();
  document.querySelectorAll('#access .current-menu-item, #access .current_page_item').forEach(function (item) { item.classList.remove('current-menu-item', 'current_page_item'); });
  document.querySelectorAll('#access [aria-current]').forEach(function (item) { item.removeAttribute('aria-current'); });
  var script = document.createElement('script');
  script.src = root + 'assets/search-index.js';
  script.onload = function () {
    var data = window.FAW_SEARCH_DATA;
    function normalize(text) { return text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('de'); }
    var terms = query.match(/-?"[^"]+"|\S+/g) || [];
    if (terms.length > 9) terms = [query];
    var results = data.pages.filter(function (page) {
      var text = normalize(page.title + ' ' + page.text);
      return terms.every(function (term) {
        var exclude = term.charAt(0) === '-';
        if (exclude) term = term.slice(1);
        var found = text.includes(normalize(term.replace(/^"|"$/g, '')));
        return exclude ? !found : found;
      });
    });
    var parsed = new DOMParser().parseFromString(results.length ? data.template : data.empty, 'text/html');
    var main = parsed.querySelector('#main');
    var content = main.querySelector('#content');
    if (results.length) {
      main.querySelector('.page-title span').textContent = query;
      main.querySelector('#breadcrumbs .current-item').textContent = "Suchergebnisse für '" + query + "'";
      var pageCount = Math.ceil(results.length / 10);
      var current = Math.min(pageCount, Math.max(1, parseInt(params.get('paged'), 10) || 1));
      results.slice((current - 1) * 10, current * 10).forEach(function (result) {
        var resultDoc = new DOMParser().parseFromString(result.html, 'text/html');
        content.append(resultDoc.querySelector('article'));
      });
      var inner = document.createElement('div'); inner.className = 'inner';
      if (pageCount > 1) {
        var nav = document.createElement('nav'); nav.id = 'nav-below'; nav.className = 'wp-pagenavi clearfix';
        function pageLink(n, label, className) {
          var el = document.createElement(n === current ? 'span' : 'a');
          el.className = n === current ? 'current' : className;
          el.textContent = label;
          if (n !== current) el.href = root + 'index.html?s=' + encodeURIComponent(query) + '&paged=' + n;
          nav.append(el);
        }
        if (current > 1) pageLink(current - 1, '←', 'previouspostslink');
        for (var n = 1; n <= pageCount; n++) pageLink(n, String(n), 'page ' + (n > current ? 'larger' : 'smaller'));
        if (current < pageCount) pageLink(current + 1, '→', 'nextpostslink');
        inner.append(nav);
      }
      content.append(inner);
    }
    document.querySelector('#main').replaceWith(main);
    document.body.className = 'search ' + (results.length ? 'search-results' : 'search-no-results') + ' wp-theme-souffle single-author scroll-to-top wide header-full-width wp38 mega-menu-enabled';
    var requestedPage = Math.max(1, parseInt(params.get('paged'), 10) || 1);
    if (requestedPage > 1) document.body.classList.add('paged', 'paged-' + requestedPage, 'search-paged-' + requestedPage);
    document.title = query + ' ‹ Suchergebnisse  ‹ FAW' + (requestedPage > 1 ? ' ‹ Seite ' + requestedPage : '');
    localLinks(main);

  };
  document.head.append(script);
}());
