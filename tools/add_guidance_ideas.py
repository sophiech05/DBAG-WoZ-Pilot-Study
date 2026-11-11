#!/usr/bin/env python3
"""Insert a collapsible operator-only guidance-ideas panel in DBAG.

Run from the repository root: python3 tools/add_guidance_ideas.py
Then review: git diff
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

MARKER = 'id="dbag-guidance-ideas"'

PANEL = r'''<!-- DBAG operator-only ideas. Optional; collapsed by default. -->
<details id="dbag-guidance-ideas" class="dbag-guidance-ideas">
  <summary>💡 Idées de guidage <span class="dbag-ideas-optional">(facultatif)</span></summary>
  <p class="dbag-ideas-intro">Quelques exemples pour vous inspirer. Adaptez-les librement aux échanges observés.</p>
  <div class="dbag-ideas-list">
    <div class="dbag-idea"><div><strong>Démarche et procédures</strong><p>Quelle serait la prochaine étape pour avancer dans votre analyse ?</p></div><button type="button" class="dbag-copy-idea" data-guidance="Quelle serait la prochaine étape pour avancer dans votre analyse ?">Copier</button></div>
    <div class="dbag-idea"><div><strong>Compréhension conceptuelle</strong><p>Comment pourriez-vous expliquer ce résultat à partir du phénomène physique étudié ?</p></div><button type="button" class="dbag-copy-idea" data-guidance="Comment pourriez-vous expliquer ce résultat à partir du phénomène physique étudié ?">Copier</button></div>
    <div class="dbag-idea"><div><strong>Raisonnement épistémique</strong><p>Qu'est-ce qui vous permet d'affirmer que vos données soutiennent cette conclusion ?</p></div><button type="button" class="dbag-copy-idea" data-guidance="Qu'est-ce qui vous permet d'affirmer que vos données soutiennent cette conclusion ?">Copier</button></div>
    <div class="dbag-idea"><div><strong>Collaboration</strong><p>Êtes-vous tous d'accord avec cette interprétation ? Pourquoi ?</p></div><button type="button" class="dbag-copy-idea" data-guidance="Êtes-vous tous d'accord avec cette interprétation ? Pourquoi ?">Copier</button></div>
    <div class="dbag-idea"><div><strong>Régulation métacognitive</strong><p>Comment pourriez-vous vérifier que votre démarche est adaptée ?</p></div><button type="button" class="dbag-copy-idea" data-guidance="Comment pourriez-vous vérifier que votre démarche est adaptée ?">Copier</button></div>
    <div class="dbag-idea"><div><strong>Régulation affective</strong><p>Qu'est-ce qui vous semble le plus difficile ou incertain à ce stade ?</p></div><button type="button" class="dbag-copy-idea" data-guidance="Qu'est-ce qui vous semble le plus difficile ou incertain à ce stade ?">Copier</button></div>
  </div>
</details>
<style>
.dbag-guidance-ideas{margin:1rem 0;border:1px solid #d8e2e2;border-radius:12px;background:#f8fbfa;color:#223c3c;overflow:hidden;font:inherit}
.dbag-guidance-ideas summary{padding:.85rem 1rem;font-weight:650;cursor:pointer}
.dbag-guidance-ideas summary:focus-visible,.dbag-copy-idea:focus-visible{outline:3px solid #328d8b;outline-offset:2px}
.dbag-ideas-optional{font-size:.8rem;font-weight:400;color:#617373}
.dbag-ideas-intro{padding:0 1rem;font-size:.85rem;color:#576e6c}
.dbag-ideas-list{padding:0 .8rem .8rem}
.dbag-idea{display:flex;align-items:center;justify-content:space-between;gap:.8rem;border-top:1px solid #e5eded;padding:.7rem .2rem}
.dbag-idea strong{font-size:.85rem}.dbag-idea p{margin:.2rem 0 0;font-size:.87rem;line-height:1.45}
.dbag-copy-idea{flex-shrink:0;border:1px solid #b6ceca;border-radius:7px;background:white;color:#225a56;padding:.45rem .65rem;cursor:pointer;font:inherit;font-size:.8rem}
.dbag-copy-idea:hover{background:#edf6f4}
@media(max-width:520px){.dbag-idea{align-items:flex-start;flex-direction:column}.dbag-copy-idea{align-self:flex-end}}
</style>
<script>
(() => {
  const panel = document.getElementById('dbag-guidance-ideas');
  if (!panel || panel.dataset.initialized) return;
  panel.dataset.initialized = 'true';
  panel.addEventListener('click', async (event) => {
    const button = event.target.closest('.dbag-copy-idea');
    if (!button || !panel.contains(button)) return;
    const guidance = button.dataset.guidance;
    if (!guidance) return;
    try {
      await navigator.clipboard.writeText(guidance);
    } catch (_) {
      const temporary = document.createElement('textarea');
      temporary.value = guidance;
      temporary.style.cssText = 'position:fixed;opacity:0';
      document.body.appendChild(temporary);
      temporary.select();
      const ok = document.execCommand('copy');
      temporary.remove();
      if (!ok) { button.textContent = 'Copie impossible'; return; }
    }
    button.textContent = 'Copié ✓';
    window.setTimeout(() => { button.textContent = 'Copier'; }, 1200);
  });
})();
</script>
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', type=Path, help='Operator HTML/Python file, if auto-detection is ambiguous')
    parser.add_argument('--dry-run', action='store_true', help='Find target without changing files')
    args = parser.parse_args()
    root = Path.cwd()
    if args.file:
        candidates = [args.file]
    else:
        candidates = [p for p in root.rglob('*') if p.suffix.lower() in ('.html', '.py')
                      and not any(part.startswith('.') or part in ('venv', 'node_modules', 'build', 'dist', '__pycache__') for part in p.relative_to(root).parts)]
    scored = []
    for path in candidates:
        if path.resolve() == Path(__file__).resolve():
            continue
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        content = path.read_text(encoding='utf-8', errors='replace')
        if MARKER in content:
            print(f'Already present: {path}')
            return 0
        if '</body>' not in content.lower():
            continue
        name = str(path).lower()
        score = (4 if ('operator' in name or 'operateur' in name or 'opérateur' in name) else 0)
        score += (3 if 'Catégorie de recherche' in content or 'Cat&eacute;gorie de recherche' in content else 0)
        score += (2 if 'Messages envoyés' in content or 'guidance' in name else 0)
        score += (1 if 'priorit' in content.lower() else 0)
        if score >= 4:
            scored.append((score, path, content))
    if not scored:
        print('No unambiguous operator page found. No file changed.', file=sys.stderr)
        print('Please provide the operator HTML/Python file, or retry with --file PATH.', file=sys.stderr)
        return 2
    scored.sort(key=lambda x: x[0], reverse=True)
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        print('Multiple candidate files; no file changed:', file=sys.stderr)
        for score, path, _ in scored:
            print(f'  {path} (score={score})', file=sys.stderr)
        print('Retry with --file PATH.', file=sys.stderr)
        return 2
    _, path, content = scored[0]
    # Inserting before the document closing tag works for both static HTML and HTML
    # embedded in Python multiline string literals, without changing existing handlers.
    idx = content.lower().rfind('</body>')
    updated = content[:idx] + PANEL + '\n' + content[idx:]
    print(f'Target: {path}')
    if args.dry_run:
        print('Dry run: no changes made.')
    else:
        path.write_text(updated, encoding='utf-8')
        print('Inserted guidance ideas. Review with: git diff')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
