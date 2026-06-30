import { useState, useRef, useEffect, useCallback } from 'react';
import s from './DevConsolePage.module.css';

// ─── Constants ────────────────────────────────────────────────────────────────
const MODEL_CATALOG = {
  claude: [
    { id: 'claude-sonnet-4-6',         name: 'Claude Sonnet 4.6', tags: ['best', '균형'],    default: true },
    { id: 'claude-opus-4-6',           name: 'Claude Opus 4.6',   tags: ['heavy', '최고성능'] },
    { id: 'claude-haiku-4-5-20251001', name: 'Claude Haiku 4.5',  tags: ['fast', 'cheap'] },
  ],
  openai: [
    { id: 'gpt-4o',      name: 'GPT-4o',      tags: ['best', '균형'], default: true },
    { id: 'gpt-4o-mini', name: 'GPT-4o mini', tags: ['fast', 'cheap'] },
    { id: 'o1-preview',  name: 'o1 preview',  tags: ['heavy', '추론'] },
  ],
  gemini: [
    { id: 'gemini-1.5-pro',   name: 'Gemini 1.5 Pro',   tags: ['best'],        default: true },
    { id: 'gemini-1.5-flash', name: 'Gemini 1.5 Flash', tags: ['fast', 'cheap'] },
    { id: 'gemini-2.0-flash', name: 'Gemini 2.0 Flash', tags: ['fast', 'best'] },
  ],
  ollama: [
    { id: 'llama3:8b',  name: 'Llama 3 8B',  tags: ['fast', 'local'], default: true },
    { id: 'llama3:70b', name: 'Llama 3 70B', tags: ['heavy', 'local'] },
    { id: 'mistral:7b', name: 'Mistral 7B',  tags: ['fast', 'local'] },
  ],
};

const PROVIDER_LABELS = {
  claude: 'Claude (Anthropic)', openai: 'OpenAI',
  gemini: 'Google Gemini',      ollama: 'Ollama (로컬)',
};

const APIKEY_DESCS = {
  claude: 'Anthropic Console → console.anthropic.com',
  openai: 'OpenAI Platform → platform.openai.com',
  gemini: 'Google AI Studio → aistudio.google.com',
  ollama: '(API Key 불필요)',
};

const API_PLACEHOLDERS = {
  claude: 'sk-ant-...', openai: 'sk-...', gemini: 'AIza...', ollama: '(불필요)',
};

const DEFAULT_SETTINGS = {
  provider:    'claude',
  model:       'claude-sonnet-4-6',
  apiKey:      '',
  endpoint:    'http://localhost:11434',
  temperature: 0.3,
  maxTokens:   4096,
  keepContext: true,
  streaming:   true,
};

const INITIAL_PROJECT_FILES = {
  'main.py':                   { status: 'clean' },
  'models/config.py':          { status: 'clean' },
  'models/signal.py':          { status: 'clean' },
  'crawler/stock_crawler.py':  { status: 'clean' },
  'crawler/naver_crawler.py':  { status: 'clean' },
  'analyzer/sentiment.py':     { status: 'clean' },
  'analyzer/signal_engine.py': { status: 'clean' },
  'scheduler/job.py':          { status: 'clean' },
  'bot/telegram_bot.py':       { status: 'clean' },
  'utils/git_watcher.py':      { status: 'clean' },
  'requirements.txt':          { status: 'clean' },
};

const SYSTEM_PROMPT = `당신은 "Stock Harness" Python 주식 분석 프로젝트의 전담 개발 AI입니다.
프로젝트: FastAPI + pykrx + 네이버토론크롤링 + KR-FinBert 감성분석 + Telegram 봇 + GitHub 자동커밋
코드 수정 시 반드시 \`\`\`python:파일경로\`\`\` 형식으로 파일명 명시. 한국어로 응답.`;

const MTAG_CLASSES = {
  best:  s.mtagBest,
  fast:  s.mtagFast,
  heavy: s.mtagHeavy,
  cheap: s.mtagCheap,
};

const BADGE_VARIANT = {
  green:  s.badgeGreen,
  amber:  s.badgeAmber,
  purple: s.badgePurple,
  blue:   s.badgeBlue,
};

const DOT_CLASS = {
  clean:    s.dotClean,
  modified: s.dotModified,
  new:      s.dotNew,
};

// ─── Helpers ──────────────────────────────────────────────────────────────────
function loadSettings() {
  try {
    const saved = localStorage.getItem('ai_settings');
    return saved ? { ...DEFAULT_SETTINGS, ...JSON.parse(saved) } : { ...DEFAULT_SETTINGS };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

function escHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function parseResponse(text) {
  const codeBlocks = [];
  let html = text;
  html = html.replace(/```(?:python:([^\n]+)|python|bash)?\n([\s\S]*?)```/g, (_, path, code) => {
    if (path) codeBlocks.push({ path: path.trim(), code: code.trim() });
    return `<pre>${escHtml(code.trim())}</pre>`;
  });
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\n/g, '<br>');
  return { html, codeBlocks };
}

function fileIcon(path) {
  if (path.endsWith('.py'))   return '🐍';
  if (path.endsWith('.html')) return '🌐';
  if (path.endsWith('.sh'))   return '⚙️';
  return '📝';
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function DevConsolePage() {
  const [view,         setView]        = useState('chat');
  const [settings,     setSettings]    = useState(loadSettings);
  const [form,         setForm]        = useState(loadSettings);
  const [messages,     setMessages]    = useState([]);
  const [isStreaming,  setIsStreaming]  = useState(false);
  const [input,        setInput]       = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileContents, setFileContents] = useState({});
  const [projectFiles, setProjectFiles] = useState(INITIAL_PROJECT_FILES);
  const [gitLog,       setGitLog]      = useState([]);
  const [commitMsg,    setCommitMsg]   = useState('');
  const [gitStatus,    setGitStatus]   = useState({ text: '🔄 git ready', variant: 'amber' });
  const [saveVisible,  setSaveVisible]  = useState(false);
  const [history,      setHistory]     = useState([]);
  const [showKey,      setShowKey]     = useState(false);

  const chatEndRef      = useRef(null);
  const textareaRef     = useRef(null);
  const autoCommitTimer = useRef(null);
  const pendingFiles    = useRef(new Set());

  useEffect(() => {
    const cfg = loadSettings();
    setMessages([{
      role: 'assistant',
      content:
        `안녕하세요! Stock Harness 전담 개발 AI입니다. 🚀\n\n현재 설정: \`${cfg.provider} / ${cfg.model}\`\n` +
        `⚙️ 상단 **AI 설정** 탭에서 모델·프로바이더를 변경할 수 있어요.\n\n요청 예시:\n` +
        `\`거래량 급등 조건을 5배로 올려줘\`\n\`텔레그램 알림 포맷 변경해줘\`\n\`scheduler/job.py 전체 보여줘\``,
    }]);
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── Git ────────────────────────────────────────────────────────────────────
  const doCommit = useCallback((message) => {
    const sha = Math.random().toString(36).slice(2, 9);
    const ts  = new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });
    setGitLog(log => [{ sha, message, ts }, ...log]);
    setGitStatus({ text: '✅ pushed', variant: 'green' });
    setProjectFiles(pf => {
      const next = { ...pf };
      for (const p of Object.keys(next)) {
        if (next[p].status !== 'new') next[p] = { ...next[p], status: 'clean' };
      }
      return next;
    });
    setTimeout(() => setGitStatus({ text: '🔄 git ready', variant: 'amber' }), 3000);
  }, []);

  const scheduleAutoCommit = useCallback((path) => {
    pendingFiles.current.add(path);
    clearTimeout(autoCommitTimer.current);
    setGitStatus({ text: `🟡 ${pendingFiles.current.size}개 대기`, variant: 'amber' });
    autoCommitTimer.current = setTimeout(() => {
      const files = Array.from(pendingFiles.current).join(', ');
      doCommit(`auto: AI 수정 - ${files}`);
      pendingFiles.current.clear();
    }, 30000);
  }, [doCommit]);

  function handleManualCommit() {
    const msg = commitMsg.trim() || `feat: 수동 커밋 ${new Date().toLocaleString('ko-KR')}`;
    doCommit(msg);
    setCommitMsg('');
  }

  // ── Code apply ─────────────────────────────────────────────────────────────
  const applyCode = useCallback((path, code) => {
    setFileContents(fc => ({ ...fc, [path]: code }));
    setProjectFiles(pf => ({
      ...pf,
      [path]: { status: pf[path] ? 'modified' : 'new' },
    }));
    setSelectedFile(path);
    scheduleAutoCommit(path);
  }, [scheduleAutoCommit]);

  // ── Send message ───────────────────────────────────────────────────────────
  async function sendMessage() {
    const text = input.trim();
    if (!text || isStreaming) return;

    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';

    const userMsg = { role: 'user', content: text };
    const msgs    = settings.keepContext
      ? [...history, { role: 'user', content: text }]
      : [{ role: 'user', content: text }];

    setMessages(prev => [...prev, userMsg, { role: 'assistant', content: '', streaming: true }]);
    setIsStreaming(true);

    try {
      const res = await fetch('/api/chat', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          model:      settings.model,
          max_tokens: settings.maxTokens,
          system:     SYSTEM_PROMPT,
          messages:   msgs,
        }),
      });

      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        throw new Error(e.error?.message || `HTTP ${res.status}`);
      }

      const reader  = res.body.getReader();
      const decoder = new TextDecoder();
      let   fullText = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        fullText += decoder.decode(value, { stream: true });
        setMessages(prev => {
          const next = [...prev];
          next[next.length - 1] = { role: 'assistant', content: fullText, streaming: true };
          return next;
        });
      }

      const { codeBlocks } = parseResponse(fullText);
      setMessages(prev => {
        const next = [...prev];
        next[next.length - 1] = { role: 'assistant', content: fullText, streaming: false, codeBlocks };
        return next;
      });

      if (settings.keepContext) {
        setHistory(h => [...h, { role: 'user', content: text }, { role: 'assistant', content: fullText }]);
      }
    } catch (e) {
      setMessages(prev => {
        const next = [...prev];
        next[next.length - 1] = { role: 'assistant', content: `오류: ${e.message}`, isError: true };
        return next;
      });
    } finally {
      setIsStreaming(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  function handleInputChange(e) {
    setInput(e.target.value);
    const ta = e.target;
    ta.style.height = 'auto';
    ta.style.height = `${Math.min(ta.scrollHeight, 120)}px`;
  }

  // ── Settings ───────────────────────────────────────────────────────────────
  function handleSelectProvider(key) {
    const defaultModel = MODEL_CATALOG[key].find(m => m.default)?.id ?? MODEL_CATALOG[key][0].id;
    setForm(f => ({ ...f, provider: key, model: defaultModel }));
  }

  function handleSaveSettings() {
    setSettings({ ...form });
    localStorage.setItem('ai_settings', JSON.stringify(form));
    setSaveVisible(true);
    setTimeout(() => setSaveVisible(false), 2000);
  }

  function handleResetSettings() {
    if (!confirm('설정을 초기값으로 되돌릴까요?')) return;
    setForm({ ...DEFAULT_SETTINGS });
    setSettings({ ...DEFAULT_SETTINGS });
    localStorage.removeItem('ai_settings');
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className={s.container}>

      {/* ── Left: File Tree ─────────────────────────────────────────────── */}
      <aside className={s.aside}>
        <div className={s.panelTitle}>프로젝트 파일</div>
        <div className={s.fileTree}>
          {Object.entries(projectFiles).map(([path, meta]) => (
            <div
              key={path}
              className={`${s.fileItem} ${selectedFile === path ? s.fileItemActive : ''}`}
              onClick={() => setSelectedFile(path)}
              title={path}
            >
              <span className={`${s.dot} ${DOT_CLASS[meta.status] ?? s.dotClean}`} />
              {fileIcon(path)} {path}
            </div>
          ))}
        </div>
        <div className={s.asideFooter}>
          <input
            className={s.commitMsgInput}
            placeholder="커밋 메시지 (비우면 자동)"
            value={commitMsg}
            onChange={e => setCommitMsg(e.target.value)}
          />
          <button className={s.gitCommitBtn} onClick={handleManualCommit}>
            ↑ GitHub Push
          </button>
        </div>
      </aside>

      {/* ── Center ──────────────────────────────────────────────────────── */}
      <div className={s.center}>
        <div className={s.innerHeader}>
          <div className={s.innerTabs}>
            <button
              className={`${s.innerTab} ${view === 'chat' ? s.innerTabActive : ''}`}
              onClick={() => setView('chat')}
            >💬 AI 채팅</button>
            <button
              className={`${s.innerTab} ${view === 'settings' ? s.innerTabActive : ''}`}
              onClick={() => setView('settings')}
            >⚙️ AI 설정</button>
          </div>
          <div className={s.badges}>
            <span className={`${s.badge} ${s.badgePurple}`}>{PROVIDER_LABELS[settings.provider]}</span>
            <span className={`${s.badge} ${s.badgeBlue}`}>{settings.model}</span>
            <span className={`${s.badge} ${BADGE_VARIANT[gitStatus.variant]}`}>{gitStatus.text}</span>
            <span className={`${s.badge} ${s.badgeGreen}`}>⎇ main</span>
          </div>
        </div>

        {view === 'chat' ? (
          <div className={s.chatView}>
            <div className={s.chatArea}>
              {messages.map((msg, i) => (
                <MessageBubble key={i} msg={msg} onApply={applyCode} />
              ))}
              <div ref={chatEndRef} />
            </div>
            <div className={s.chatInputRow}>
              <textarea
                ref={textareaRef}
                className={s.userInput}
                rows={1}
                placeholder="구현할 기능을 설명하세요. 예: '거래량 조건 5배로 올려줘'"
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
              />
              <button
                className={s.sendBtn}
                onClick={sendMessage}
                disabled={isStreaming}
              >전송 ↵</button>
            </div>
          </div>
        ) : (
          <SettingsView
            form={form}
            setForm={setForm}
            onSelectProvider={handleSelectProvider}
            onSave={handleSaveSettings}
            onReset={handleResetSettings}
            saveVisible={saveVisible}
            showKey={showKey}
            setShowKey={setShowKey}
          />
        )}
      </div>

      {/* ── Right: File Panel ────────────────────────────────────────────── */}
      <div className={s.filePanel}>
        <div className={s.aiSummary}>
          <div className={s.summaryRow}>
            <span className={s.summaryLabel}>프로바이더</span>
            <span className={`${s.summaryVal} ${s.summaryHighlight}`}>{PROVIDER_LABELS[settings.provider]}</span>
          </div>
          <div className={s.summaryRow}>
            <span className={s.summaryLabel}>모델</span>
            <span className={`${s.summaryVal} ${s.summaryHighlight}`}>{settings.model}</span>
          </div>
          <div className={s.summaryRow}>
            <span className={s.summaryLabel}>Temperature</span>
            <span className={s.summaryVal}>{settings.temperature}</span>
          </div>
          <div className={s.summaryRow}>
            <span className={s.summaryLabel}>Max Tokens</span>
            <span className={s.summaryVal}>{settings.maxTokens}</span>
          </div>
        </div>
        <div className={s.filePanelHeader}>
          <span className={s.fileName}>{selectedFile ?? '파일을 선택하세요'}</span>
        </div>
        <div className={s.fileContent} style={!selectedFile ? { color: 'var(--muted)', fontFamily: 'sans-serif', fontSize: 13 } : {}}>
          {selectedFile
            ? (fileContents[selectedFile] ?? `// ${selectedFile}\n// AI에게 "show ${selectedFile}" 라고 요청하세요`)
            : '좌측 파일 목록에서 파일을 클릭하면 내용이 표시됩니다.'}
        </div>
        <div className={s.panelTitle} style={{ padding: '10px 16px 4px' }}>Git 커밋 로그</div>
        <div className={s.gitLogPanel}>
          {gitLog.map((entry, i) => (
            <div key={i} className={s.gitEntry}>
              <span className={s.gitSha}>{entry.sha}</span>
              {entry.message}
              <span className={s.gitTs}>{entry.ts}</span>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────
function MessageBubble({ msg, onApply }) {
  const [applied, setApplied] = useState({});
  const isUser = msg.role === 'user';
  const { html, codeBlocks } = parseResponse(msg.content || '');

  if (msg.streaming && !msg.content) {
    return (
      <div className={`${s.msg} ${s.msgAssistant}`}>
        <div className={s.typingIndicator}>
          <span className={s.typingDot} />
          <span className={s.typingDot} />
          <span className={s.typingDot} />
        </div>
      </div>
    );
  }

  return (
    <div className={`${s.msg} ${isUser ? s.msgUser : s.msgAssistant}`}>
      <div
        className={`${isUser ? s.msgBubbleUser : s.msgBubbleAssistant} ${msg.isError ? s.msgError : ''}`}
        dangerouslySetInnerHTML={{ __html: msg.streaming ? html + '▍' : html }}
      />
      {!msg.streaming && codeBlocks?.map((block, i) => (
        <button
          key={i}
          className={s.applyBtn}
          disabled={applied[i]}
          onClick={() => {
            onApply(block.path, block.code);
            setApplied(a => ({ ...a, [i]: true }));
          }}
        >
          {applied[i] ? `✓ ${block.path} 적용됨` : `✅ ${block.path}에 적용`}
        </button>
      ))}
    </div>
  );
}

function Toggle({ on, onChange }) {
  return (
    <div className={s.toggleWrap} onClick={() => onChange(!on)}>
      <div className={`${s.toggleTrack} ${on ? s.toggleTrackOn : ''}`}>
        <div className={s.toggleKnob} />
      </div>
      <span className={s.toggleLabel}>{on ? '켜짐' : '꺼짐'}</span>
    </div>
  );
}

function SettingsView({ form, setForm, onSelectProvider, onSave, onReset, saveVisible, showKey, setShowKey }) {
  const models = MODEL_CATALOG[form.provider];

  const PROVIDERS = [
    { key: 'claude', name: '🟣 Claude (Anthropic)', desc: 'Sonnet·Opus 등 고성능 모델. Claude Code 공식 API 사용.',  badge: '기본값', badgeClass: 'pbadgeDefault' },
    { key: 'openai', name: '🟢 OpenAI',              desc: 'GPT-4o, o1 등. OpenAI API Key 필요.',                    badge: '선택',   badgeClass: 'pbadgeBeta' },
    { key: 'gemini', name: '🔵 Google Gemini',        desc: 'Gemini 1.5 Pro·Flash. Google AI Studio Key 필요.',       badge: '선택',   badgeClass: 'pbadgeBeta' },
    { key: 'ollama', name: '⚫ Ollama (로컬)',         desc: '로컬 LLM (Llama3, Mistral 등). 인터넷 불필요.',           badge: '로컬',   badgeClass: 'pbadgeLocal' },
  ];

  return (
    <div className={s.settingsView}>

      {/* 1. 프로바이더 */}
      <div className={s.settingsSection}>
        <h2 className={s.sectionTitle}>AI 프로바이더 <span className={s.sectionTag}>기본값</span></h2>
        <div className={s.providerGrid}>
          {PROVIDERS.map(p => (
            <div
              key={p.key}
              className={`${s.providerCard} ${form.provider === p.key ? s.providerCardSelected : ''}`}
              onClick={() => onSelectProvider(p.key)}
            >
              <div className={s.pcheck} />
              <div className={s.pname}>{p.name}</div>
              <div className={s.pdesc}>{p.desc}</div>
              <span className={`${s.pbadge} ${s[p.badgeClass]}`}>{p.badge}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 2. 모델 */}
      <div className={s.settingsSection}>
        <h2 className={s.sectionTitle}>
          모델 선택 <span className={s.sectionTag}>{PROVIDER_LABELS[form.provider]}</span>
        </h2>
        <div className={s.modelGrid}>
          {models.map(m => (
            <div
              key={m.id}
              className={`${s.modelCard} ${form.model === m.id ? s.modelCardSelected : ''}`}
              onClick={() => setForm(f => ({ ...f, model: m.id }))}
            >
              <div className={s.mname}>{m.name}</div>
              <div className={s.mcode}>{m.id}</div>
              <div className={s.mtags}>
                {m.tags.map(t => (
                  <span key={t} className={`${s.mtag} ${MTAG_CLASSES[t] ?? ''}`}>{t}</span>
                ))}
              </div>
              {m.default && <div className={s.modelDefault}>★ 기본값</div>}
            </div>
          ))}
        </div>
      </div>

      {/* 3. API Key */}
      <div className={s.settingsSection}>
        <h2 className={s.sectionTitle}>API 키 / 엔드포인트</h2>
        <div className={s.paramRow}>
          <div>
            <div className={s.paramLabel}>API Key</div>
            <div className={s.paramDesc}>{APIKEY_DESCS[form.provider]}</div>
          </div>
          <div className={s.paramInputWrap}>
            <input
              type={showKey ? 'text' : 'password'}
              className={s.paramInput}
              style={{ paddingRight: 72 }}
              placeholder={API_PLACEHOLDERS[form.provider]}
              value={form.apiKey}
              disabled={form.provider === 'ollama'}
              onChange={e => setForm(f => ({ ...f, apiKey: e.target.value }))}
            />
            <span className={s.keyToggle} onClick={() => setShowKey(!showKey)}>
              {showKey ? '숨기기' : '보기'}
            </span>
          </div>
        </div>
        {form.provider === 'ollama' && (
          <div className={s.paramRow}>
            <div>
              <div className={s.paramLabel}>엔드포인트</div>
              <div className={s.paramDesc}>Ollama 서버 주소</div>
            </div>
            <div className={s.paramInputWrap}>
              <input
                type="text"
                className={s.paramInput}
                placeholder="http://localhost:11434"
                value={form.endpoint}
                onChange={e => setForm(f => ({ ...f, endpoint: e.target.value }))}
              />
            </div>
          </div>
        )}
      </div>

      {/* 4. 파라미터 */}
      <div className={s.settingsSection}>
        <h2 className={s.sectionTitle}>파라미터 튜닝</h2>
        <div className={s.paramRow}>
          <div>
            <div className={s.paramLabel}>Temperature</div>
            <div className={s.paramDesc}>창의성 ↕ 일관성 (코드 생성 권장: 0.2~0.5)</div>
          </div>
          <div className={s.paramInputWrap}>
            <input
              type="range" min="0" max="1" step="0.05"
              className={s.rangeInput}
              value={form.temperature}
              onChange={e => setForm(f => ({ ...f, temperature: parseFloat(e.target.value) }))}
            />
            <span className={s.paramVal}>{form.temperature}</span>
          </div>
        </div>
        <div className={s.paramRow}>
          <div>
            <div className={s.paramLabel}>Max Tokens</div>
            <div className={s.paramDesc}>응답 최대 길이</div>
          </div>
          <div className={s.paramInputWrap}>
            <input
              type="range" min="256" max="8192" step="256"
              className={s.rangeInput}
              value={form.maxTokens}
              onChange={e => setForm(f => ({ ...f, maxTokens: parseInt(e.target.value) }))}
            />
            <span className={s.paramVal}>{form.maxTokens}</span>
          </div>
        </div>
        <div className={s.paramRow}>
          <div>
            <div className={s.paramLabel}>Context 유지</div>
            <div className={s.paramDesc}>이전 대화 기억 (꺼두면 매 요청 독립)</div>
          </div>
          <div className={s.paramInputWrap}>
            <Toggle on={form.keepContext} onChange={val => setForm(f => ({ ...f, keepContext: val }))} />
          </div>
        </div>
        <div className={s.paramRow}>
          <div>
            <div className={s.paramLabel}>스트리밍</div>
            <div className={s.paramDesc}>응답을 실시간으로 표시</div>
          </div>
          <div className={s.paramInputWrap}>
            <Toggle on={form.streaming} onChange={val => setForm(f => ({ ...f, streaming: val }))} />
          </div>
        </div>
      </div>

      {/* 5. 저장 */}
      <div className={s.saveRow}>
        <button className={s.btnPrimary} onClick={onSave}>✅ 설정 저장</button>
        <button className={s.btnGhost}   onClick={onReset}>↺ 초기화</button>
        {saveVisible && <span className={s.saveMsg}>저장 완료!</span>}
      </div>

    </div>
  );
}
