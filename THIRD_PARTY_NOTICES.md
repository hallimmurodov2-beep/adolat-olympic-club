# Third-party components

The application source is supplied under the root MIT license. The following locally bundled components retain their own licenses and notices:

| Component | Purpose | Included notice |
| --- | --- | --- |
| MathJax TeX-to-SVG bundle | Local mathematical typesetting; no remote service | `static/vendor/MathJax-LICENSE` (Apache License 2.0) |
| Prism core and language grammars | Source-code syntax highlighting; no execution | `static/vendor/Prism-LICENSE` (MIT) |

MathJax: https://www.mathjax.org/ ; source: https://github.com/mathjax/MathJax-src

Prism: https://prismjs.com/ ; source: https://github.com/PrismJS/prism

These vendor bundles were taken from the corresponding packages available in the development environment. Preserve the bundled notices when redistributing. Package manifests pin the directly tested Python/TypeScript versions; a deployment should resolve and audit its complete transitive dependencies and keep a deployment-specific lock/SBOM. Third-party Python packages, the TypeScript compiler, PostgreSQL, container base images, and test tools are installed separately and retain their upstream licenses. No font files are included. System fonts and MathJax SVG paths are used.

The separately invoked demonstration seed is not an imported competition collection. It contains illustrative school-level exercises and synthetic records, not real students or licensed Olympiad archives. School staff must check correctness, suitability, and rights before using any demonstration content or uploading their own collections. This software license does not grant rights to teacher-uploaded content or student work.
