// KaTeX rendering. Two components:
// - <Tex src="..." />         a pure math expression.
// - <TexInline text="..."/>   mixed text with $...$ math spans, so descriptions like "Distance from $\omega$ to ..." render correctly with real spaces between words.
import { useEffect, useRef } from 'react';
import katex from 'katex';

export function Tex({ src, block = false }: { src: string; block?: boolean }) {
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    try {
      katex.render(src, ref.current, {
        throwOnError: false,
        displayMode: block,
        output: 'html',
      });
    } catch {
      ref.current.textContent = src;
    }
  }, [src, block]);
  return <span ref={ref} className={block ? 'tex-block' : 'tex-inline'} />;
}

export function TexInline({ text }: { text: string }) {
  // Split on $...$ pairs. Even indices are plain text, odd indices are math.
  const parts = text.split(/\$([^$]+)\$/g);
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 0
          ? <span key={i}>{part}</span>
          : <Tex key={i} src={part} />
      )}
    </>
  );
}