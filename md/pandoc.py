#!/usr/bin/env python
import panflute as pf
import os
import sys
import subprocess
# import pygraphviz
import hashlib

def h1hr(elem, doc):
    """
    Add a bottom border to all the <h1>s
    """
    if not isinstance(elem, pf.Header):
        return None

    if elem.level != 1:
        return None

    elem.attributes['style'] = 'border-bottom:1px solid #cccccc'
    return elem

def bq(elem, doc):
    """
    Add a ::: bq div to make a <blockquote>
    """
    if not isinstance(elem, pf.Div):
        return None

    if elem.classes == ['bq']:
        return pf.BlockQuote(*elem.content)

    if 'std' in elem.classes:
        return pf.Div(pf.BlockQuote(*elem.content), classes=elem.classes)

def sha1(x):
    return hashlib.sha1(x.encode(sys.getfilesystemencoding())).hexdigest()

MD_DIR = os.path.dirname(__file__)

def graphviz(elem, doc):
    if isinstance(elem, pf.CodeBlock) and 'graphviz' in elem.classes:
        code = elem.text
        G = pygraphviz.AGraph(string=code)
        G.layout(prog='dot')

        filename = sha1(code)
        filetype = {'html': 'png', 'latex': 'pdf'}.get(doc.format, 'png')
        caption = elem.attributes.get('caption', '')
        imagedir = f'{MD_DIR}/graphviz-images'
        src = f'{imagedir}/{filename}.{filetype}'
        if not os.path.isfile(src):
            try:
                os.mkdir(imagedir)
                sys.stderr.write(f'Created directory {imagedir}\n')
            except OSError:
                pass
            G.draw(src)
            sys.stderr.write(f'Created image {src}\n')
        return pf.Para(pf.Image(pf.Str(caption), url=src, title=caption))

def mermaid(elem, doc):
    if isinstance(elem, pf.CodeBlock) and 'mermaid' in elem.classes:
        code = elem.text
        caption = elem.attributes.get('caption', '')
        filename = sha1(code)

        mermaid_dir = f'{MD_DIR}/mermaid-images'
        src_file = f'{mermaid_dir}/{filename}.mmd'
        dst_img = f'{mermaid_dir}/{filename}.svg'
        if not os.path.isfile(src_file):
            try:
                os.mkdir(mermaid_dir)
                sys.stderr.write(f'Created directory {mermaid_dir}\n')
            except OSError:
                pass

            with open(src_file, 'w') as f:
                f.write(code)

            subprocess.check_call(['mmdc', '-i', src_file, '-o', dst_img],
                stderr=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL)
        return pf.Para(pf.Image(pf.Str(caption), url=dst_img, title=caption))

def op(elem, doc):
    if isinstance(elem, pf.Code) and 'op' in elem.classes:
        return pf.RawInline(f'<code><span class="op">{elem.text}</span></code>')

if __name__ == '__main__':
    # pf.run_filters([h1hr, bq, graphviz, mermaid, op])
    pf.run_filters([h1hr, bq, mermaid, op])
