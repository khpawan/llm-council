import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import Stage1 from './Stage1';
import Stage2 from './Stage2';
import Stage3 from './Stage3';
import AlgorithmToolbar from './AlgorithmToolbar';
import ExportButton from './ExportButton';
import './ChatInterface.css';

export default function ChatInterface({
  conversation,
  onSendMessage,
  isLoading,
  algorithm,
  onAlgorithmChange,
}) {
  const [input, setInput] = useState('');
  const [loadedFileName, setLoadedFileName] = useState('');
  const [uploadError, setUploadError] = useState('');
  const [isDraggingFile, setIsDraggingFile] = useState(false);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversation]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input);
      setInput('');
      setLoadedFileName('');
      setUploadError('');
    }
  };

  const handleKeyDown = (e) => {
    // Submit on Enter (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handlePickFile = () => {
    fileInputRef.current?.click();
  };

  const readMarkdownFile = async (file) => {
    const isMarkdownFile =
      file.name.toLowerCase().endsWith('.md') ||
      file.type === 'text/markdown' ||
      file.type === 'text/x-markdown';

    if (!isMarkdownFile) {
      setUploadError('Only Markdown (.md) files are supported.');
      return;
    }

    try {
      const fileText = await file.text();
      setInput((prev) => (prev.trim() ? `${prev}\n\n${fileText}` : fileText));
      setLoadedFileName(file.name);
      setUploadError('');
    } catch {
      setUploadError(`Could not read ${file.name}.`);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) {
      return;
    }

    await readMarkdownFile(file);
    e.target.value = '';
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    if (!isLoading) {
      setIsDraggingFile(true);
    }
  };

  const handleDragLeave = (e) => {
    if (e.currentTarget.contains(e.relatedTarget)) {
      return;
    }
    setIsDraggingFile(false);
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    setIsDraggingFile(false);

    if (isLoading) {
      return;
    }

    const file = e.dataTransfer.files?.[0];
    if (!file) {
      return;
    }

    await readMarkdownFile(file);
  };

  if (!conversation) {
    return (
      <div className="chat-interface">
        <div className="empty-state">
          <h2>Welcome to LLM Council</h2>
          <p>Create a new conversation to get started</p>
        </div>
      </div>
    );
  }

  // Helper to find the user query preceding an assistant message
  const getQueryForIndex = (index) => {
    for (let i = index - 1; i >= 0; i--) {
      if (conversation.messages[i].role === 'user') {
        return conversation.messages[i].content;
      }
    }
    return '';
  };

  return (
    <div className="chat-interface">
      <div className="messages-container">
        {conversation.messages.length === 0 ? (
          <div className="empty-state">
            <h2>Start a conversation</h2>
            <p>Ask a question to consult the LLM Council</p>
          </div>
        ) : (
          conversation.messages.map((msg, index) => (
            <div key={index} className="message-group">
              {msg.role === 'user' ? (
                <div className="user-message">
                  <div className="message-label">You</div>
                  <div className="message-content">
                    <div className="markdown-content">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="assistant-message">
                  <div className="message-label">
                    LLM Council
                    {msg.stage3 && (
                      <ExportButton message={msg} query={getQueryForIndex(index)} />
                    )}
                  </div>

                  {/* Stage 1 */}
                  {msg.loading?.stage1 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Stage 1: Collecting responses from council models...</span>
                    </div>
                  )}
                  {msg.stage1 && <Stage1 responses={msg.stage1} />}

                  {/* Stage 2 */}
                  {msg.loading?.stage2 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Stage 2: Peer review in progress...</span>
                    </div>
                  )}
                  {msg.stage2 && (
                    <Stage2
                      rankings={msg.stage2}
                      labelToModel={msg.metadata?.label_to_model}
                      aggregateRankings={msg.metadata?.aggregate_rankings}
                    />
                  )}

                  {/* Stage 3 */}
                  {msg.loading?.stage3 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Stage 3: Synthesizing final answer...</span>
                    </div>
                  )}
                  {msg.stage3 && <Stage3 finalResponse={msg.stage3} />}
                </div>
              )}
            </div>
          ))
        )}

        {isLoading && (
          <div className="loading-indicator">
            <div className="spinner"></div>
            <span>Consulting the council...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <AlgorithmToolbar algorithm={algorithm} onChange={onAlgorithmChange} />

      <form className="input-form" onSubmit={handleSubmit}>
        <div
          className={`composer ${isDraggingFile ? 'drag-active' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <div className="composer-toolbar">
            <input
              ref={fileInputRef}
              type="file"
              accept=".md,text/markdown"
              className="file-input"
              onChange={handleFileUpload}
            />
            <button
              type="button"
              className="upload-button"
              onClick={handlePickFile}
              disabled={isLoading}
            >
              Upload .md
            </button>
            {loadedFileName && (
              <span className="file-status">Loaded: {loadedFileName}</span>
            )}
          </div>
          {uploadError && (
            <div className="upload-error">{uploadError}</div>
          )}
          {isDraggingFile && (
            <div className="drop-hint">Drop your Markdown file here</div>
          )}
          <textarea
            className="message-input"
            placeholder="Ask your question or upload a Markdown file... (Shift+Enter for new line, Enter to send)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            rows={3}
          />
        </div>
        <button
          type="submit"
          className="send-button"
          disabled={!input.trim() || isLoading}
        >
          Send
        </button>
      </form>
    </div>
  );
}
