"""Regenerate the `const S = {...}` schema block in run.workflow.js from schemas/*.schema.json,
and write <run-dir>/workflow-args.json for an article prepared by prepare.py.

Usage: python3 pipeline/build_workflow.py <run-dir>
"""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); PROJECT = os.path.dirname(HERE)
schemas = {f[:2]: json.load(open(os.path.join(HERE, 'schemas', f))) for f in sorted(os.listdir(os.path.join(HERE, 'schemas')))}
for v in schemas.values(): v.pop('$schema', None)
p = os.path.join(HERE, 'run.workflow.js'); s = open(p).read()
s = re.sub(r'const S = \{.*\n', 'const S = ' + json.dumps(schemas, ensure_ascii=False) + '\n', s, count=1)
if s != open(p).read(): open(p, 'w').write(s)  # leave a plugin install untouched unless schemas changed
run = os.path.abspath(sys.argv[1]); b = json.load(open(os.path.join(run, 'bundle.json')))
args = {'project': PROJECT, 'run': run, 'article_path': b['identity']['article_path'], 'identity': b['identity'],
        'prompt_files': {f[:2]: 'prompts/' + f for f in sorted(os.listdir(os.path.join(PROJECT, 'prompts'))) if f[:2].isdigit()}}
json.dump(args, open(os.path.join(run, 'workflow-args.json'), 'w'), indent=1)
print(json.dumps(args))
