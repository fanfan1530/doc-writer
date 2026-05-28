# CLAUDE.md — 智慧警务智能工作台

## Project Overview
AI-powered police document assistant platform. React 18 + Vite 5 frontend, Python FastAPI + SQLAlchemy 2.0 async backend. Supports: AI document generation, case search/analysis, legal knowledge base, AI copilot chat with tool calls.

## Architecture

```
frontend/  (port 5178)          backend/  (port 8091)
├─ React 18 + Vite 5            ├─ FastAPI + SQLAlchemy 2.0 async
├─ Ant Design 5 + Tailwind      ├─ SQLite (dev) / PostgreSQL (prod)
├─ React Router 6 (lazy)        ├─ ChromaDB (case vector search)
├─ Axios + JWT interceptors     ├─ SSE streaming (copilot chat)
├─ ErrorBoundary (prod-grade)   ├─ Prometheus metrics (/metrics)
└─ CSS @media print             └─ Redis optional (rate limit + cache)
```

## Key File Map

### Frontend (`frontend/src/`)
| File | Purpose |
|------|---------|
| `App_v3.tsx` | Main router with lazy-loaded routes |
| `api/client.ts` | Axios instance + JWT auth + refresh queue |
| `context/AppContext.tsx` | Global state: models, shared transcript, generation task |
| `hooks/useIdleTimer.ts` | 30min idle timeout with 60s warning |
| `components/ErrorBoundary.tsx` | Production error boundary with retry + resetKeys |
| `components/layout/AppLayout.tsx` | Sidebar + top bar + auth guard shell |
| `components/ChatPanel.tsx` | SSE streaming copilot chat with tool call viz |
| `components/document/DocumentGenPage.tsx` | Dual-pane AI/manual document generation |
| `components/DocumentPreview.tsx` | Paper-style preview with print/download |
| `components/cases/CaseSearchPage.tsx` | Semantic case search + detail drawer |
| `components/analysis/CaseAnalysisPage.tsx` | Timeline extraction + case nature analysis |
| `components/dashboard/DashboardPage.tsx` | Stats + sparklines + system status |
| `components/knowledge/KnowledgeBasePage.tsx` | Law search with debounce + highlighting |

### Backend (`backend/app/`)
| File | Purpose |
|------|---------|
| `main.py` | FastAPI app factory, middleware chain, lifespan startup |
| `api/generation.py` | Document generation + history + timeline + file upload |
| `api/copilot.py` | SSE chat + conversation CRUD + LLM title gen |
| `api/cases.py` | Case vector search + detail + seed |
| `api/knowledge.py` | Law pagination + search + stats |
| `services/document_service.py` | Generation orchestrator: LLM → field processing → template fill |
| `services/copilot_service.py` | SSE streaming + multi-round tool calling (max 3) |
| `services/case_service.py` | ChromaDB vector search + keyword fallback |
| `core/tools.py` | 8 copilot tool definitions + ToolExecutor |
| `core/llm_client.py` | OpenAI + Anthropic unified client (httpx) |
| `core/security.py` | Input sanitization + rate limiter (Redis/memory) |
| `core/monitoring.py` | Prometheus counters: LLM calls, doc generations |
| `core/export/docx_exporter.py` | Gov-formatted Word export |
| `core/rag_retriever.py` | Hybrid keyword+vector law/template retrieval |
| `infrastructure/models.py` | 8 ORM models (User, GenerationHistory, Law, etc.) |
| `infrastructure/database.py` | Async SQLAlchemy engine + session factory |
| `middleware/request_timing.py` | JSON access logging + X-Process-Time header |

## Key Patterns
- **Auth**: JWT access + refresh tokens, localStorage vs sessionStorage via "remember me"
- **SSE**: Service yields pre-formatted strings; API layer re-parses to save full reply
- **Tool calls**: Multi-round (max 3), parallel `asyncio.gather`, `role: "tool"` format
- **Error handling**: ErrorBoundary with resetKeys on route change; LLM retry with exponential backoff
- **Pagination**: Offset-based with server-side sort in history API
- **DB indexes**: Composite `(doc_type, created_at)` on generation_history

## Running
```bash
# Frontend (from frontend/)
npm install && npm run dev

# Backend (from backend/)
pip install -e . && uvicorn app.main:app --host 0.0.0.0 --port 8091 --reload
```

## RBAC System (v2.1)

Five police roles with granular permissions defined in `backend/app/core/security.py`:

| Role | Key | Permissions |
|------|-----|-------------|
| System Admin | `system_admin` | All (users, roles, audit, cases, documents, models, knowledge, analytics, copilot) |
| Unit Leader | `unit_leader` | Read cases/docs, approve/reject docs, view analytics, use copilot |
| Case Officer | `case_officer` | Read/write cases & docs, use copilot, read knowledge |
| Reviewer | `reviewer` | Read cases/docs, approve/reject docs, use copilot |
| Auditor | `auditor` | Read-only: cases, docs, audit logs, analytics, knowledge |

**Key files:**
- `backend/app/core/security.py` — `ROLE_PERMISSIONS`, `ROLE_LABELS`, `require_permission()`, `get_user_permissions()`
- `backend/app/api/admin.py` — User CRUD, role assignment, status toggle, audit log queries
- `backend/app/api/auth.py` — Login/register now returns `permissions[]`, `role_label`, `display_name`, `unit`
- `backend/app/middleware/auth.py` — Sets `request.state.permissions` from JWT role
- `backend/app/infrastructure/models.py` — `AuditLog` model + `User` gained `display_name`, `unit`, `updated_at`
- `frontend/src/context/AppContext.tsx` — `userInfo`, `userPermissions`, `userRole`, `hasPermission()`
- `frontend/src/components/layout/Sidebar.tsx` — Dynamic menu filtering by permissions
- `frontend/src/components/admin/UserManagementPage.tsx` — User list + role dropdown + enable/disable
- `frontend/src/components/admin/AuditLogPage.tsx` — Audit timeline + filter by user/action

**Permission check pattern (backend):**
```python
@router.get("/admin/users")
async def list_users(..., _=Depends(require_permission("users:read"))):
    ...
```

**Permission check pattern (frontend):**
```tsx
const { hasPermission } = useAppContext();
{hasPermission('users:read') && <AdminMenuItem />}
```

## Database Persistence (v2.1)

- `backend/app/infrastructure/database.py` — PostgreSQL support with connection pooling (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`), `pool_pre_ping` + `pool_recycle`
- `backend/app/infrastructure/repository.py` — `BaseRepository[T]` with `get_by_id`, `get_or_404`, `list_all` (paginated), `create`, `update`, `delete`, `count`, `exists`, `bulk_create`
- `backend/app/config.py` — Centralized settings: `database_url`, `redis_url`, `chroma_persist_dir`, `jwt_*`

**Repository usage:**
```python
class UserRepo(BaseRepository[User]):
    model = User

repo = UserRepo()
users, total = await repo.list_all(User.is_active == True, limit=20, offset=0)
user = await repo.get_or_404(user_id)
```

## Case Lifecycle Management (v2.1)

**State machine:** `FILING → INVESTIGATING → REVIEWING → APPROVED → CLOSED → ARCHIVED`

**New ORM models** in `backend/app/infrastructure/models.py`:
- `Case` — case_number, title, case_type, status, officer_id, unit, description, incident_date, location
- `CaseDocument` — links generation_history to case, with DRAFT/SUBMITTED/APPROVED/REJECTED status
- `CaseEvidence` — evidence items with type, file_path, uploaded_by
- `CaseTimeline` — event log (auto-recorded on status changes, document submits, reviews)
- `ReviewRecord` — document review actions (APPROVE/REJECT/RETURN)

**Key files:**
- `backend/app/services/case_service.py` — `CaseService` with `create_case`, `transition_status`, `submit_document`, `review_document`; also retains ChromaDB `search_cases`/`seed_cases` for backward compat
- `backend/app/api/cases.py` — Full CRUD: `GET/POST /api/cases`, `GET/PUT /api/cases/db/{id}`, `POST /api/cases/db/{id}/transition`, `POST /api/cases/db/{id}/documents`, `POST /api/cases/db/{id}/documents/{doc_id}/review`
- `frontend/src/components/cases/CaseListPage.tsx` — Table with status/type filters, keyword search, create button
- `frontend/src/components/cases/CaseDetailPage.tsx` — Full detail with Descriptions + Timeline + documents table + reviews table + status transition selector
- `frontend/src/components/cases/CaseCreateModal.tsx` — Create form (title, type, unit, date, location, description)
- `frontend/src/components/cases/CaseStatusBadge.tsx` — 7 color-coded status tags

**Routes:** `/cases/manage` → CaseListPage, `/cases/manage/:id` → CaseDetailPage

## Real-Time Notifications (v2.1)

**Notification types:** `CASE_ASSIGNED`, `DOCUMENT_SUBMITTED`, `DOCUMENT_APPROVED`, `DOCUMENT_REJECTED`, `DEADLINE_WARNING`, `SYSTEM_ANNOUNCEMENT`

**Key files:**
- `backend/app/infrastructure/models.py` — `Notification` model (user_id, type, title, content, related_case_id, is_read)
- `backend/app/services/notification_service.py` — `NotificationService` with `create`, `list_notifications`, `mark_read`, `mark_all_read`, `get_unread_count`; WebSocket client management (`ws_connect`/`ws_disconnect`/`ws_broadcast`)
- `backend/app/api/notifications.py` — `GET /api/notifications`, `GET /api/notifications/unread-count`, `PUT /api/notifications/{id}/read`, `POST /api/notifications/mark-all-read`
- `backend/app/api/ws.py` — `WebSocket /ws/notifications?token=<jwt>` with JWT auth + ping/pong heartbeat
- `frontend/src/hooks/useWebSocket.ts` — Auto-reconnect WebSocket hook with JWT token and heartbeat
- `frontend/src/components/notifications/NotificationCenter.tsx` — Dropdown panel with list + click-to-read + mark all read + case link
- `frontend/src/components/layout/AppLayout.tsx` — Bell icon + unread badge + WebSocket connection
- `frontend/vite.config.ts` — `/ws` proxy for WebSocket in dev mode

## Advanced Analytics (v2.1)

**API endpoints** (all require `analytics:read` permission):
- `GET /api/analytics/overview` — total cases, documents, users, closed rate, monthly new
- `GET /api/analytics/case-trends?months=12` — by month, by type, by status
- `GET /api/analytics/officer-stats?limit=10` — officer performance ranking
- `GET /api/analytics/document-stats` — by doc type, avg latency, token usage

**Key files:**
- `backend/app/services/analytics_service.py` — Aggregate queries with SQLAlchemy func/group_by
- `backend/app/api/analytics.py` — 4 endpoints, all permission-guarded
- `frontend/src/components/analytics/AnalyticsDashboard.tsx` — Full dashboard with:
  - 4 stat cards (cases, docs, users, closed rate)
  - LineChart: monthly case trends (recharts)
  - PieChart: case type distribution
  - BarChart: case status distribution
  - Table: officer performance ranking
  - Table: document generation statistics with summary row
- `frontend/package.json` — added `recharts` dependency
