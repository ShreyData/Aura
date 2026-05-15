import React, { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { codeToHtml } from 'shiki';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface MarkdownProps {
  content: string;
  className?: string;
}

export const Markdown: React.FC<MarkdownProps> = ({ content, className }) => {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      className={cn('prose prose-invert max-w-none break-words prose-pre:bg-transparent prose-pre:p-0', className)}
      components={{
        code: (props: any) => {
          const { children, className, node, ...rest } = props;
          const match = /language-(\w+)/.exec(className || '');
          const [highlighted, setHighlighted] = useState<string | null>(null);

          useEffect(() => {
            if (match) {
              codeToHtml(String(children).replace(/\n$/, ''), {
                lang: match[1],
                theme: 'github-dark',
              }).then(setHighlighted);
            }
          }, [children, match]);

          if (match && highlighted) {
            return (
              <div 
                className="my-2 rounded-lg border border-gray-700 bg-gray-900/50 overflow-hidden"
                dangerouslySetInnerHTML={{ __html: highlighted }} 
              />
            );
          }

          if (match) {
            return (
              <pre className="bg-gray-900 border border-gray-700 p-4 rounded-lg my-2 overflow-x-auto">
                <code className={className} {...rest}>
                  {children}
                </code>
              </pre>
            );
          }

          return (
            <code className="bg-gray-800 px-1.5 py-0.5 rounded text-sm font-mono text-blue-300" {...rest}>
              {children}
            </code>
          );
        },
      }}
    >
      {content}
    </ReactMarkdown>
  );
};
