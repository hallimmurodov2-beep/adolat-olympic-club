/* Restrict TeX to local, non-HTML packages. No remote extensions or services. */
window.MathJax = {
  startup: { typeset: false },
  tex: {
    inlineMath: [['$', '$'], ['\\(', '\\)']],
    displayMath: [['$$', '$$'], ['\\[', '\\]']],
    packages: ['base', 'ams', 'newcommand', 'noerrors', 'noundefined'],
    maxBuffer: 30000, maxMacros: 1000
  },
  svg: { fontCache: 'local' },
  options: { enableMenu: false, skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code'] }
};
window.Prism = { manual: true };
