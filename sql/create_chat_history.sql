-- Supabase schema for chat history
CREATE TABLE chat_history (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chat_history_user_id
ON chat_history(user_id);

CREATE INDEX idx_chat_history_created_at
ON chat_history(created_at);
