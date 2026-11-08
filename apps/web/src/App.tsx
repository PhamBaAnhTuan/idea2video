import {useEffect, useMemo, useState, type FormEvent} from 'react';
import {ArrowDown, AudioLines, Check, ChevronDown, ChevronUp, Clapperboard, FileAudio, FileText, LoaderCircle, Sparkles, Upload, Video, WandSparkles} from 'lucide-react';
import type {Project, ProjectSummary} from './types';

const API = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';

function formatTime(seconds: number) {
  const totalMs = Math.max(0, Math.round(seconds * 1000));
  const whole = Math.floor(totalMs / 1000);
  const minutes = Math.floor(whole / 60);
  const secs = whole % 60;
  const millis = totalMs % 1000;
  return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}.${String(millis).padStart(3, '0')}`;
}
const stages = [
  {id: 'script', title: 'Kịch bản', subtitle: 'Gemini hoặc nội dung có sẵn', icon: Sparkles},
  {id: 'tts', title: 'Giọng đọc', subtitle: 'VieNeu hoặc audio có sẵn', icon: AudioLines},
  {id: 'alignment', title: 'Căn chỉnh audio', subtitle: 'STT · timestamp từng từ', icon: FileAudio},
  {id: 'timeline', title: 'Timeline phụ đề', subtitle: 'SRT + JSON', icon: FileText},
  {id: 'render', title: 'Dựng video', subtitle: 'Remotion render', icon: Clapperboard},
];
const videoTemplates = [
  {id: 'cinematic', title: 'Điện ảnh', description: 'Thẻ cảnh tối giản, chuyển động nhẹ', preview: 'cinematic'},
  {id: 'captions', title: 'Chữ nổi bật', description: 'Tiêu đề lớn, phụ đề kiểu kinetic', preview: 'captions'},
  {id: 'bullet_list', title: 'Gạch đầu dòng', description: 'Làm nổi bật từng ý chính', preview: 'bullets'},
  {id: 'table', title: 'Bảng tóm tắt', description: 'Trình bày ý chính theo hàng', preview: 'table'},
  {id: 'chart', title: 'Biểu đồ nhịp độ', description: 'So sánh thời lượng từng cảnh', preview: 'chart'},
] as const;
type VideoTemplate = typeof videoTemplates[number]['id'];

export default function App() {
  const [idea, setIdea] = useState('Giải thích trí tuệ nhân tạo đang thay đổi cách chúng ta học tập và làm việc như thế nào.');
  const [scriptSource, setScriptSource] = useState<'generate' | 'provided'>('generate');
  const [scriptFormat, setScriptFormat] = useState<'text' | 'json'>('text');
  const [scriptContent, setScriptContent] = useState('');
  const [scriptFileName, setScriptFileName] = useState('');
  const [audioSource, setAudioSource] = useState<'tts' | 'upload'>('tts');
  const [audioFiles, setAudioFiles] = useState<File[]>([]);
  const [audience, setAudience] = useState('Sinh viên và người xem phổ thông');
  const [tone, setTone] = useState('Dễ hiểu, gần gũi, có ví dụ thực tế');
  const [duration, setDuration] = useState(1);
  const [aspect, setAspect] = useState<'9:16' | '16:9' | '1:1'>('9:16');
  const [voice, setVoice] = useState('Hải Đăng');
  const [projectName, setProjectName] = useState('');
  const [videoTemplate, setVideoTemplate] = useState<VideoTemplate>('cinematic');
  const [project, setProject] = useState<Project | null>(null);
  const [projectHistory, setProjectHistory] = useState<ProjectSummary[]>([]);
  const [historySort, setHistorySort] = useState<'recent' | 'name'>('recent');
  const [historyError, setHistoryError] = useState('');
  const [loading, setLoading] = useState(false);
  const [apiState, setApiState] = useState<{gemini_configured: boolean; stt_configured: boolean; stt_backend: string; stt_runtime_found: boolean; renderer_found: boolean} | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    fetch(`${API}/api/config`).then(r => r.json()).then(setApiState).catch(() => setApiState(null));
  }, []);

  useEffect(() => {
    let cancelled = false;
    const refresh = async () => {
      try {
        const response = await fetch(`${API}/api/projects?limit=100`);
        if (!response.ok) throw new Error('Không tải được danh sách dự án.');
        const data: {projects: ProjectSummary[]} = await response.json();
        if (!cancelled) {
          setProjectHistory(data.projects);
          setHistoryError('');
        }
      } catch (e) {
        if (!cancelled) setHistoryError(e instanceof Error ? e.message : 'Lỗi khi tải danh sách dự án.');
      }
    };
    void refresh();
    return () => {cancelled = true;};
  }, []);

  useEffect(() => {
    if (!project?.id || project.status === 'completed' || project.status === 'failed') return;
    let cancelled = false;
    const timer = window.setInterval(async () => {
      try {
        const response = await fetch(`${API}/api/projects/${project.id}`);
        if (!response.ok) throw new Error('Không đọc được trạng thái dự án.');
        const next: Project = await response.json();
        if (!cancelled) {
          setProject(next);
          setProjectHistory(current => current.map(item => item.id === next.id
            ? {
              ...item,
              name: next.name || item.name,
              status: next.status,
              stage: next.stage,
              progress: next.progress,
              updated_at: new Date().toISOString(),
            }
            : item));
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Lỗi kết nối API.');
      }
    }, 2000);
    return () => {cancelled = true; window.clearInterval(timer);};
  }, [project?.id, project?.status]);

  const videoUrl = useMemo(() => project?.artifacts?.video ? `${API}${project.artifacts.video}` : '', [project]);
  const sortedProjectHistory = useMemo(() => [...projectHistory].sort((a, b) => (
    historySort === 'name'
      ? a.name.localeCompare(b.name, 'vi')
      : b.created_at.localeCompare(a.created_at)
  )), [historySort, projectHistory]);
  const selectedStage = stages.findIndex(stage => stage.id === project?.current_step);
  const providedSceneCount = useMemo(() => {
    if (scriptSource !== 'provided' || !scriptContent.trim()) return null;
    if (scriptFormat === 'json') {
      try {
        const parsed: unknown = JSON.parse(scriptContent.replace(/^\uFEFF/, ''));
        if (typeof parsed === 'object' && parsed !== null && 'scenes' in parsed && Array.isArray(parsed.scenes)) {
          return parsed.scenes.length;
        }
        return null;
      } catch {
        return null;
      }
    }
    return scriptContent.split(/\n\s*\n/).filter(part => part.trim()).length;
  }, [scriptContent, scriptFormat, scriptSource]);
  const audioCountMismatch = scriptSource === 'provided'
    && audioSource === 'upload'
    && providedSceneCount !== null
    && audioFiles.length > 0
    && providedSceneCount !== audioFiles.length;
  const currentStage = project?.status === 'completed'
    ? stages.length
    : selectedStage >= 0
      ? selectedStage
      : project?.status === 'failed'
        ? -1
        : Math.min(stages.length - 1, Math.max(0, Math.floor((project?.progress || 0) / 20)));

  async function loadScriptFile(file?: File) {
    if (!file) return;
    const format = file.name.toLowerCase().endsWith('.json') ? 'json' : 'text';
    try {
      setScriptContent(await file.text());
      setScriptFormat(format);
      setScriptFileName(file.name);
      setError('');
    } catch {
      setError('Không đọc được file kịch bản. Hãy chọn lại file .txt hoặc .json.');
    }
  }

  function moveAudioFile(index: number, offset: number) {
    setAudioFiles(files => {
      const target = index + offset;
      if (target < 0 || target >= files.length) return files;
      const reordered = [...files];
      [reordered[index], reordered[target]] = [reordered[target], reordered[index]];
      return reordered;
    });
  }

  async function openProject(projectId: string) {
    setError('');
    try {
      const response = await fetch(`${API}/api/projects/${projectId}`);
      if (!response.ok) throw new Error('Không mở được dự án đã lưu.');
      const savedProject: Project = await response.json();
      setProject(savedProject);
      setProjectName(savedProject.name ?? '');
      if (savedProject.video_template) setVideoTemplate(savedProject.video_template);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Lỗi khi mở dự án.');
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(''); setProject(null); setLoading(true);
    try {
      if (scriptSource === 'provided' && !scriptContent.trim()) {
        throw new Error('Hãy tải file hoặc nhập nội dung kịch bản có sẵn.');
      }
      if (audioSource === 'upload' && audioFiles.length === 0) {
        throw new Error('Hãy tải lên audio cho từng cảnh trong kịch bản.');
      }
      const requestData = {
        project_name: projectName.trim(),
        video_template: videoTemplate,
        idea: scriptSource === 'generate' ? idea : idea.trim(),
        audience, tone, duration_minutes: duration, aspect_ratio: aspect, voice,
        script_source: scriptSource,
        script_format: scriptFormat,
        script_content: scriptSource === 'provided' ? scriptContent : null,
        audio_source: audioSource,
      };
      const formData = new FormData();
      formData.append('request_data', JSON.stringify(requestData));
      if (audioSource === 'upload') {
        audioFiles.forEach(file => formData.append('audio_files', file, file.name));
      }
      const response = await fetch(`${API}/api/projects/import`, {method: 'POST', body: formData});
      const data = await response.json();
      if (!response.ok) {
        const detail = Array.isArray(data.detail)
          ? data.detail.map((item: {msg?: string}) => item.msg).filter(Boolean).join(' ')
          : data.detail;
        throw new Error(detail || 'Không tạo được dự án.');
      }
      const createdAt = new Date().toISOString();
      const newProject: Project = {
        id: data.id,
        name: data.name,
        video_template: data.video_template,
        status: data.status,
        stage: data.stage,
        progress: 0,
      };
      setProject(newProject);
      setProjectHistory(current => [{
        id: data.id,
        name: data.name,
        status: data.status,
        stage: data.stage,
        progress: 0,
        created_at: createdAt,
        updated_at: createdAt,
        video_template: data.video_template,
      }, ...current.filter(item => item.id !== data.id)]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Không thể kết nối API.');
    } finally { setLoading(false); }
  }

  const stepStatus = (id: string, index: number) => project?.steps?.[id as keyof NonNullable<Project['steps']>]
    ?? (project?.status === 'completed' || currentStage > index
      ? 'completed'
      : currentStage === index
        ? 'running'
        : 'pending');

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand"><div className="brand-mark"><WandSparkles size={20}/></div><div><strong>IDEA TO VIDEO</strong><span>Vietnamese AI video studio</span></div></div>
        <div className="top-pill"><span className="pulse-dot"/> Local workspace</div>
      </header>

      <section className="hero">
        <div className="eyebrow"><span/> AUTOMATED VIDEO WORKFLOW</div>
        <h1>Biến ý tưởng thành<br/><em>một câu chuyện có hình.</em></h1>
        <p>Từ ý tưởng ban đầu đến kịch bản, giọng đọc tiếng Việt, phụ đề khớp audio và video hoàn chỉnh — trong một pipeline.</p>
      </section>

      <section className="workflow" aria-label="Quy trình">
        {stages.map((stage, i) => {
          const Icon = stage.icon;
          const status = stepStatus(stage.id, i);
          const done = status === 'completed';
          const skipped = status === 'skipped';
          const failed = status === 'failed';
          const active = project?.status === 'running' && (status === 'running' || currentStage === i);
          return <div className={`workflow-step ${done ? 'done' : ''} ${skipped ? 'skipped' : ''} ${failed ? 'failed' : ''} ${active ? 'active' : ''}`} key={stage.id}>
            <div className="step-icon">{done ? <Check size={18}/> : skipped ? <ArrowDown size={18}/> : failed ? '!' : <Icon size={18}/>}</div>
            <div><b>{stage.title}</b><small>{skipped ? 'Đã bỏ qua · dùng dữ liệu có sẵn' : failed ? 'Bước thất bại' : stage.subtitle}</small></div>
            {i < stages.length - 1 && <ArrowDown className="step-arrow" size={15}/>}
          </div>;
        })}
      </section>

      <div className="content-grid">
        <section className="panel form-panel">
          <div className="panel-heading"><div><span className="section-kicker">01 / INPUT</span><h2>Bắt đầu với ý tưởng</h2></div><span className="number-chip">NEW PROJECT</span></div>
          <form onSubmit={submit}>
            <div className="field">
              <label className="field-label" htmlFor="project-name">Tên dự án</label>
              <input id="project-name" value={projectName} onChange={event => setProjectName(event.target.value)} maxLength={100} placeholder="Để trống để tự lấy từ ý tưởng hoặc tiêu đề kịch bản"/>
              <p className="input-hint">Tên này dùng để nhận diện và sắp xếp dự án trong danh sách bên cạnh.</p>
            </div>
            <div className="input-section">
              <div className="input-section-heading"><Sparkles size={16}/><div><b>01 · Kịch bản</b><small>Chọn tạo mới hoặc dùng nội dung có sẵn</small></div></div>
              <div className="choice-row" role="group" aria-label="Nguồn kịch bản">
                <button type="button" aria-pressed={scriptSource === 'generate'} className={scriptSource === 'generate' ? 'choice active' : 'choice'} onClick={() => setScriptSource('generate')}>Tạo bằng Gemini</button>
                <button type="button" aria-pressed={scriptSource === 'provided'} className={scriptSource === 'provided' ? 'choice active' : 'choice'} onClick={() => setScriptSource('provided')}>Tôi đã có kịch bản</button>
              </div>
              {scriptSource === 'generate' ? <>
                <label className="field-label" htmlFor="idea">Ý tưởng video <span>*</span></label>
                <textarea id="idea" value={idea} onChange={e => setIdea(e.target.value)} minLength={10} maxLength={3000} required placeholder="Mô tả chủ đề, thông điệp hoặc câu chuyện bạn muốn kể..." />
              </> : <>
                <label className="field-label" htmlFor="script-file">File kịch bản .txt hoặc .json</label>
                <div className="file-picker">
                  <input id="script-file" type="file" accept=".txt,.json,text/plain,application/json" onChange={event => void loadScriptFile(event.target.files?.[0])}/>
                  <Upload size={16}/><span>{scriptFileName || 'Chọn file hoặc dán nội dung bên dưới'}</span>
                </div>
                <label className="field-label" htmlFor="script-content">Nội dung kịch bản <span>*</span></label>
                <textarea id="script-content" className="script-input" value={scriptContent} onChange={event => {setScriptContent(event.target.value); setScriptFileName(''); setScriptFormat('text');}} required placeholder={'Dán lời thoại ở đây. Với file .txt, ngăn cách các cảnh bằng một dòng trống.\n\nMỗi đoạn văn sẽ trở thành một cảnh.'}/>
                <p className="input-hint">JSON dùng cấu trúc video_title / hook / scenes. Text sẽ được chia cảnh theo các đoạn trống.</p>
              </>}
            </div>
            <div className="field-row">
              <div className="field"><label className="field-label" htmlFor="audience">Đối tượng người xem</label><input id="audience" value={audience} onChange={e => setAudience(e.target.value)}/></div>
              <div className="field"><label className="field-label" htmlFor="tone">Phong cách lời dẫn</label><input id="tone" value={tone} onChange={e => setTone(e.target.value)}/></div>
            </div>
            <div className="field-row three">
              <div className="field"><label className="field-label" htmlFor="duration">Thời lượng</label><select id="duration" value={duration} onChange={e => setDuration(Number(e.target.value))}>{[1,2,3,5,8,10].map(v=><option key={v} value={v}>{v} phút</option>)}</select></div>
              <div className="field"><label className="field-label" htmlFor="aspect">Tỷ lệ khung hình</label><select id="aspect" value={aspect} onChange={e => setAspect(e.target.value as typeof aspect)}><option value="9:16">9:16 · Shorts</option><option value="16:9">16:9 · YouTube</option><option value="1:1">1:1 · Square</option></select></div>
              {audioSource === 'tts' && <div className="field"><label className="field-label" htmlFor="voice">Giọng VieNeu</label><select id="voice" value={voice} onChange={e => setVoice(e.target.value)}>{['Hải Đăng','Mai Anh','Thùy Dung','Quang Sơn','Ngọc Huyền','Trúc Ly','Phạm Tuyên'].map(v=><option key={v}>{v}</option>)}</select></div>}
            </div>
            <div className="input-section template-section">
              <div className="input-section-heading"><Clapperboard size={16}/><div><b>03 · Template video</b><small>Chọn cách trình bày nội dung khi dựng</small></div></div>
              <div className="template-grid" role="group" aria-label="Template video">
                {videoTemplates.map(template => (
                  <button
                    key={template.id}
                    type="button"
                    aria-pressed={videoTemplate === template.id}
                    className={`template-card ${videoTemplate === template.id ? 'active' : ''}`}
                    onClick={() => setVideoTemplate(template.id)}
                  >
                    <span className={`template-preview ${template.preview}`} aria-hidden="true">
                      <i/><i/><i/><i/>
                    </span>
                    <b>{template.title}</b>
                    <small>{template.description}</small>
                  </button>
                ))}
              </div>
              {videoTemplate === 'chart' && <p className="input-hint">Biểu đồ hiển thị thời lượng audio thật của từng cảnh, không suy đoán số liệu chủ đề.</p>}
            </div>
            <div className="input-section audio-section">
              <div className="input-section-heading"><AudioLines size={16}/><div><b>02 · Âm thanh</b><small>Có thể bỏ qua TTS nếu đã có file audio</small></div></div>
              <div className="choice-row" role="group" aria-label="Nguồn âm thanh">
                <button type="button" aria-pressed={audioSource === 'tts'} className={audioSource === 'tts' ? 'choice active' : 'choice'} onClick={() => setAudioSource('tts')}>Tạo giọng VieNeu</button>
                <button type="button" aria-pressed={audioSource === 'upload'} className={audioSource === 'upload' ? 'choice active' : 'choice'} onClick={() => {setAudioFiles([]); setAudioSource('upload');}}>Upload audio có sẵn</button>
              </div>
              {audioSource === 'upload' && <>
                <label className="field-label" htmlFor="audio-files">Audio theo thứ tự cảnh <span>*</span></label>
                <div className="file-picker">
                  <input id="audio-files" type="file" accept=".wav,.mp3,.m4a,.aac,.flac,.ogg,audio/*" multiple onChange={event => setAudioFiles(Array.from(event.target.files ?? []))}/>
                  <Upload size={16}/><span>{audioFiles.length ? `Đã chọn ${audioFiles.length} file · tối đa 100 MB/file` : 'Chọn MP3/WAV, theo đúng thứ tự các cảnh'}</span>
                </div>
                {audioFiles.length > 0 && <ol className="selected-files">{audioFiles.map((file, index) => <li key={`${file.name}-${index}`}><span>Cảnh {index + 1} · {file.name}</span><div className="file-order-controls"><button type="button" aria-label={`Đưa ${file.name} lên`} disabled={index === 0} onClick={() => moveAudioFile(index, -1)}><ChevronUp size={13}/></button><button type="button" aria-label={`Đưa ${file.name} xuống`} disabled={index === audioFiles.length - 1} onClick={() => moveAudioFile(index, 1)}><ChevronDown size={13}/></button></div></li>)}</ol>}
                <p className={`input-hint ${audioCountMismatch ? 'invalid' : ''}`}>{scriptSource === 'generate' ? 'Gemini sẽ tạo đúng số cảnh theo số file audio. ' : `Kịch bản có ${providedSceneCount ?? '?'} cảnh; hiện có ${audioFiles.length} file audio. `}Có thể dùng nút lên/xuống để xếp file theo thứ tự cảnh. Audio sẽ được chuẩn hóa trước khi căn chỉnh.</p>
              </>}
            </div>
            <button className="primary-button" disabled={loading || project?.status === 'running' || (scriptSource === 'generate' && !idea.trim()) || (scriptSource === 'provided' && !scriptContent.trim()) || (audioSource === 'upload' && audioFiles.length === 0) || audioCountMismatch} type="submit">
              {loading ? <LoaderCircle className="spin" size={18}/> : <Sparkles size={18}/>} Tạo video <span>→</span>
            </button>
            <p className="form-note">Các bước có dữ liệu sẵn sẽ tự bỏ qua; căn chỉnh, timeline và render vẫn chạy để hoàn thiện video.</p>
          </form>
          {apiState && <div className="integrations">
            <div className={apiState.gemini_configured ? 'ok' : 'warn'}><span/>{apiState.gemini_configured ? 'Gemini key đã cấu hình' : 'Thiếu Gemini API key'}</div>
            <div className={apiState.stt_runtime_found ? 'ok' : 'warn'}><span/>{apiState.stt_backend === 'whisper' ? (apiState.stt_runtime_found ? 'faster-whisper đã cài' : 'Chưa cài faster-whisper') : (apiState.stt_runtime_found ? 'speech-to-subtitle đã cài' : 'Chưa cài speech-to-subtitle')}</div>
            <div className={apiState.stt_configured ? 'ok' : 'warn'}><span/>{apiState.stt_configured ? `STT ${apiState.stt_backend.toUpperCase()} đã cấu hình` : apiState.stt_backend === 'mai' ? 'Thiếu OpenRouter API key cho STT' : 'Thiếu thành phần cần thiết cho STT'}</div>
            <div className={apiState.renderer_found ? 'ok' : 'warn'}><span/>{apiState.renderer_found ? 'Remotion renderer sẵn sàng' : 'Thiếu Remotion renderer'}</div>
          </div>}
        </section>

        <section className="panel output-panel">
          <div className="panel-heading"><div><span className="section-kicker">02 / OUTPUT</span><h2>Tiến trình dự án</h2></div><span className="live-tag"><span/> LIVE</span></div>
          <div className="project-history">
            <div className="history-heading"><b>Dự án đã lưu</b><select aria-label="Sắp xếp dự án" value={historySort} onChange={event => setHistorySort(event.target.value as typeof historySort)}><option value="recent">Mới nhất</option><option value="name">Tên A–Z</option></select></div>
            {historyError && <p className="history-error">{historyError}</p>}
            {sortedProjectHistory.length === 0
              ? <p className="history-empty">Dự án mới tạo sẽ xuất hiện ở đây.</p>
              : <div className="history-list">{sortedProjectHistory.slice(0, 100).map(item => (
                <button key={item.id} type="button" className={`history-item ${project?.id === item.id ? 'selected' : ''}`} onClick={() => void openProject(item.id)}>
                  <span className={`history-status ${item.status}`}/>
                  <span className="history-copy"><b>{item.name}</b><small>{item.stage || item.status} · {new Date(item.created_at).toLocaleDateString()}</small></span>
                  <span className="history-template">{videoTemplates.find(template => template.id === item.video_template)?.title ?? 'Điện ảnh'}</span>
                </button>
              ))}</div>}
          </div>
          {!project && <div className="empty-state"><div className="empty-graphic"><Video size={42}/><span>✦</span></div><h3>Video của bạn sẽ xuất hiện ở đây</h3><p>Nhập ý tưởng và bấm tạo video để bắt đầu pipeline tự động.</p><div className="mini-flow"><span>IDEA</span><i>→</i><span>SCRIPT</span><i>→</i><span>AUDIO</span><i>→</i><span>VIDEO</span></div></div>}
          {project && <div className="project-state">
            <div className="status-line"><span className={`status-badge ${project.status}`}>{project.status === 'completed' ? 'COMPLETED' : project.status === 'failed' ? 'FAILED' : project.status === 'queued' ? 'QUEUED' : 'PROCESSING'}</span><span className="project-id">ID · {project.id.slice(0, 8)}</span></div>
            <h3 className="active-project-name">{project.name || 'Dự án'}<span>{videoTemplates.find(template => template.id === project.video_template)?.title ?? 'Điện ảnh'}</span></h3>
            <div className="progress-copy"><b>{project.stage}</b><strong>{project.progress}%</strong></div>
            <div className="progress-track"><div style={{width: `${project.progress}%`}}/></div>
            <div className="progress-stages">
              {stages.map((stage, i) => {
                const status = stepStatus(stage.id, i);
                return <div key={stage.id} className={status === 'completed' ? 'stage-done' : status === 'skipped' ? 'stage-skipped' : status === 'failed' ? 'stage-failed' : currentStage === i ? 'stage-current' : ''}>
                  <span>{status === 'completed' ? '✓' : status === 'skipped' ? '↷' : status === 'failed' ? '!' : String(i + 1).padStart(2, '0')}</span>{stage.title}
                  {status === 'skipped' && <small>Đã bỏ qua</small>}
                </div>;
              })}
            </div>
            {project.error && <div className="error-box"><b>Pipeline gặp lỗi</b><p>{project.error}</p><small>Xem pipeline-error.txt trong thư mục data của dự án để biết chi tiết.</small></div>}
            {project.script && <div className="script-preview"><div className="preview-title">KỊCH BẢN · {project.script.scenes.length} CẢNH</div><h3>{project.script.video_title}</h3>{project.script.scenes.map(scene=><div className="script-scene" key={scene.id}><b>{String(scene.id).padStart(2,'0')} / {scene.scene_title}</b><p>{scene.narration}</p></div>)}</div>}
            {project.status === 'completed' && project.timeline && <>
              <div className="result-meta"><div><b>{Math.round(project.timeline.duration_seconds)}s</b><span>Thời lượng</span></div><div><b>{project.timeline.scenes.length}</b><span>Cảnh</span></div><div><b>{project.timeline.sentences.length}</b><span>Mốc câu</span></div></div>
              <div className="video-wrap"><video controls src={videoUrl}/></div>
              <div className="timeline-preview">
                <div className="preview-title">SENTENCE TIMELINE · {project.timeline.sentences.length} MỐC</div>
                {project.timeline.sentences.slice(0, 12).map(sentence => <div className="timeline-row" key={sentence.id}>
                  <time>{formatTime(sentence.start)} – {formatTime(sentence.end)}</time>
                  <p>{sentence.text}</p>
                </div>)}
                {project.timeline.sentences.length > 12 && <small className="more-timeline">Còn {project.timeline.sentences.length - 12} mốc trong timeline.json / subtitles.srt.</small>}
              </div>
              <div className="downloads">
                {project.artifacts?.subtitles_srt && <a href={`${API}${project.artifacts.subtitles_srt}`} download><FileText size={16}/> Tải SRT</a>}
                {project.artifacts?.timeline_json && <a href={`${API}${project.artifacts.timeline_json}`} download><FileAudio size={16}/> Timeline JSON</a>}
                {project.artifacts?.script_json && <a href={`${API}${project.artifacts.script_json}`} download><FileText size={16}/> Script JSON</a>}
                {project.artifacts?.words_json && <a href={`${API}${project.artifacts.words_json}`} download><AudioLines size={16}/> Word timing</a>}
              </div>
            </>}
          </div>}
          {error && <div className="error-box"><p>{error}</p></div>}
        </section>
      </div>
      <footer><span>IDEA TO VIDEO STUDIO</span><span>Gemini × VieNeu-TTS × speech-to-subtitle × Remotion</span></footer>
    </main>
  );
}
