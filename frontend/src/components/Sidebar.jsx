import './Sidebar.css';

export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onDeleteConversation,
  onNewConversation,
  onOpenSettings,
}) {
  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h1>LLM Council</h1>
        <div className="sidebar-header-buttons">
          <button className="new-conversation-btn" onClick={onNewConversation}>
            + New Conversation
          </button>
          <button className="settings-btn" onClick={onOpenSettings} title="Settings">
            &#9881;
          </button>
        </div>
      </div>

      <div className="conversation-list">
        {conversations.length === 0 ? (
          <div className="no-conversations">No conversations yet</div>
        ) : (
          conversations.map((conv) => (
            <div
              key={conv.id}
              className={`conversation-item ${
                conv.id === currentConversationId ? 'active' : ''
              }`}
              onClick={() => onSelectConversation(conv.id)}
            >
              <div className="conversation-main">
                <div className="conversation-title">
                  {conv.title || 'New Conversation'}
                </div>
                <div className="conversation-meta">
                  {conv.message_count} messages
                </div>
              </div>
              <button
                type="button"
                className="delete-conversation-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteConversation(conv.id, conv.title || 'New Conversation');
                }}
                title="Delete conversation"
                aria-label={`Delete ${conv.title || 'New Conversation'}`}
              >
                &times;
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
