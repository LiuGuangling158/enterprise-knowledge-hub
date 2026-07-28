CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS tenants (
  id VARCHAR(64) PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS departments (
  id VARCHAR(64) PRIMARY KEY,
  tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(id),
  name VARCHAR(120) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS users (
  id VARCHAR(64) PRIMARY KEY,
  tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(id),
  department_id VARCHAR(64) NOT NULL REFERENCES departments(id),
  email VARCHAR(160) NOT NULL UNIQUE,
  name VARCHAR(80) NOT NULL,
  role VARCHAR(40) NOT NULL DEFAULT 'member',
  password_hash VARCHAR(160) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS documents (
  id VARCHAR(64) PRIMARY KEY,
  tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(id),
  department_id VARCHAR(64) NOT NULL REFERENCES departments(id),
  title VARCHAR(240) NOT NULL,
  content TEXT NOT NULL,
  author_id VARCHAR(64) NOT NULL REFERENCES users(id),
  status VARCHAR(40) NOT NULL DEFAULT 'draft',
  visibility VARCHAR(40) NOT NULL DEFAULT 'department',
  version INTEGER NOT NULL DEFAULT 1,
  tags_json TEXT NOT NULL DEFAULT '[]',
  summary TEXT NOT NULL DEFAULT '',
  reads INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS document_uploads (
  id VARCHAR(64) PRIMARY KEY,
  document_id VARCHAR(64) NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(id),
  department_id VARCHAR(64) NOT NULL REFERENCES departments(id),
  uploader_id VARCHAR(64) NOT NULL REFERENCES users(id),
  original_filename VARCHAR(240) NOT NULL,
  stored_path VARCHAR(500) NOT NULL,
  content_type VARCHAR(120) NOT NULL DEFAULT 'application/octet-stream',
  size_bytes INTEGER NOT NULL,
  parser VARCHAR(80) NOT NULL,
  status VARCHAR(40) NOT NULL DEFAULT 'parsed',
  error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS document_versions (
  id VARCHAR(64) PRIMARY KEY,
  document_id VARCHAR(64) NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  version INTEGER NOT NULL,
  title VARCHAR(240) NOT NULL,
  content TEXT NOT NULL,
  summary TEXT NOT NULL DEFAULT '',
  created_by VARCHAR(64) NOT NULL REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS approvals (
  id VARCHAR(64) PRIMARY KEY,
  document_id VARCHAR(64) NOT NULL REFERENCES documents(id),
  submitter_id VARCHAR(64) NOT NULL REFERENCES users(id),
  reviewer_id VARCHAR(64) REFERENCES users(id),
  status VARCHAR(40) NOT NULL DEFAULT 'pending',
  summary TEXT NOT NULL DEFAULT '',
  reason TEXT,
  submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  reviewed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS document_acl (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  document_id VARCHAR(64) NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  subject_type VARCHAR(20) NOT NULL,
  subject_id VARCHAR(64) NOT NULL,
  permission VARCHAR(20) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_traces (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(id),
  session_id UUID NOT NULL,
  user_id VARCHAR(64) NOT NULL REFERENCES users(id),
  status VARCHAR(40) NOT NULL,
  spans JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_documents_tenant_department ON documents (tenant_id, department_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents (status);
CREATE INDEX IF NOT EXISTS idx_document_uploads_document_id ON document_uploads (document_id);
CREATE INDEX IF NOT EXISTS idx_document_uploads_tenant_created ON document_uploads (tenant_id, created_at);
CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals (status);
