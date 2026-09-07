import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { Check, Copy } from "lucide-react";

interface MarkdownContentProps {
  content: string;
}

export const MarkdownContent: React.FC<MarkdownContentProps> = ({ content }) => {
  return (
    <div className="markdown-body text-[13px] text-[#E6EDF3] font-sans leading-relaxed break-words space-y-2 select-text">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        components={{
          table: ({ node, ...props }) => (
            <div className="overflow-x-auto my-2.5 rounded-[4px] border border-[#263241] bg-[#0B0F14]">
              <table className="w-full text-left border-collapse text-[13px] text-[#E6EDF3]" {...props} />
            </div>
          ),
          thead: ({ node, ...props }) => (
            <thead className="bg-[#121821] border-b border-[#263241]" {...props} />
          ),
          tbody: ({ node, ...props }) => (
            <tbody className="divide-y divide-[#263241]" {...props} />
          ),
          tr: ({ node, ...props }) => (
            <tr className="hover:bg-[#121821]/50 transition-colors" {...props} />
          ),
          th: ({ node, ...props }) => (
            <th
              className="px-3 py-1.5 text-[12px] font-mono font-semibold text-[#8B949E] border-r border-[#263241] last:border-r-0 whitespace-nowrap"
              {...props}
            />
          ),
          td: ({ node, ...props }) => (
            <td
              className="px-3 py-1.5 text-[13px] text-[#E6EDF3] border-r border-[#263241] last:border-r-0 align-top leading-snug"
              {...props}
            />
          ),
          h1: ({ node, ...props }) => (
            <h1 className="text-[15px] font-semibold text-[#E6EDF3] mt-3 mb-1.5 border-b border-[#263241] pb-1 font-sans" {...props} />
          ),
          h2: ({ node, ...props }) => (
            <h2 className="text-[14px] font-semibold text-[#E6EDF3] mt-2.5 mb-1 font-sans" {...props} />
          ),
          h3: ({ node, ...props }) => (
            <h3 className="text-[13px] font-semibold text-[#4C8DF6] mt-2 mb-1 font-sans" {...props} />
          ),
          h4: ({ node, ...props }) => (
            <h4 className="text-[13px] font-medium text-[#8B949E] mt-1.5 mb-0.5 font-sans" {...props} />
          ),
          p: ({ node, ...props }) => (
            <p className="my-1.5 leading-relaxed" {...props} />
          ),
          ul: ({ node, ...props }) => (
            <ul className="list-disc list-outside pl-4 my-1.5 space-y-0.5" {...props} />
          ),
          ol: ({ node, ...props }) => (
            <ol className="list-decimal list-outside pl-4 my-1.5 space-y-0.5 font-mono text-[12px]" {...props} />
          ),
          li: ({ node, ...props }) => (
            <li className="pl-0.5 text-[13px] text-[#E6EDF3] leading-relaxed" {...props} />
          ),
          strong: ({ node, ...props }) => (
            <strong className="font-semibold text-[#E6EDF3]" {...props} />
          ),
          em: ({ node, ...props }) => (
            <em className="italic text-[#8B949E]" {...props} />
          ),
          hr: ({ node, ...props }) => (
            <hr className="border-t border-[#263241] my-3" {...props} />
          ),
          blockquote: ({ node, ...props }) => (
            <blockquote
              className="border-l-2 border-[#4C8DF6] bg-[#121821] pl-3 py-1.5 my-2 text-[12px] text-[#8B949E] italic rounded-r-[4px]"
              {...props}
            />
          ),
          code: ({ node, className, children, ...props }) => {
            const match = /language-(\w+)/.exec(className || "");
            const isInline = !match && !String(children).includes("\n");
            if (isInline) {
              return (
                <code
                  className="px-1 py-0.5 bg-[#1B2431] border border-[#263241] rounded-[2px] font-mono text-[12px] text-[#4C8DF6]"
                  {...props}
                >
                  {children}
                </code>
              );
            }
            return <CodeBlock language={match ? match[1] : ""}>{String(children).replace(/\n$/, "")}</CodeBlock>;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};

interface CodeBlockProps {
  language?: string;
  children: string;
}

const CodeBlock: React.FC<CodeBlockProps> = ({ language, children }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(children);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-2.5 rounded-[4px] border border-[#263241] bg-[#0B0F14] overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1 bg-[#121821] border-b border-[#263241] text-[11px] font-mono text-[#8B949E] select-none">
        <span>{language ? language.toUpperCase() : "CODE"}</span>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1 hover:text-[#E6EDF3] transition-colors cursor-pointer"
          title="Copy code"
        >
          {copied ? (
            <>
              <Check className="w-3 h-3 text-[#10B981]" />
              <span className="text-[#10B981]">Copied</span>
            </>
          ) : (
            <>
              <Copy className="w-3 h-3" />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <div className="p-3 overflow-x-auto font-mono text-[12px] text-[#E6EDF3] leading-relaxed select-text">
        <pre>{children}</pre>
      </div>
    </div>
  );
};
