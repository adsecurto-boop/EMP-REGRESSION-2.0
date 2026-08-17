import React, { useState, useEffect, useMemo } from 'react';
import {
  ImageIcon,
  Download,
  ExternalLink,
  Search,
  Filter,
  Maximize2,
  RefreshCw,
  FolderOpen,
  Calendar,
  Layers,
  HardDrive,
  FileCheck,
  Eye,
  CheckCircle2,
  ShieldCheck,
  AlertCircle
} from 'lucide-react';

export interface EvidenceFileItem {
  filename: string;
  relativePath?: string;
  fullPath?: string;
  sizeBytes: number;
  mtime: string;
  type: 'screenshot_proof' | 'html_report' | 'json_report' | 'other';
  evidenceId?: string;
  isEV013?: boolean;
  base64?: string;
}

interface EvidenceGalleryProps {
  onExportZip?: () => void;
  isExportingZip?: boolean;
}

export const EvidenceGallery: React.FC<EvidenceGalleryProps> = ({
  onExportZip,
  isExportingZip = false
}) => {
  const [evidenceFiles, setEvidenceFiles] = useState<EvidenceFileItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedFilter, setSelectedFilter] = useState<'ALL' | 'EV013' | 'SCREENSHOTS' | 'REPORTS'>('EV013');
  const [activePreviewItem, setActivePreviewItem] = useState<EvidenceFileItem | null>(null);
  const [copiedNotification, setCopiedNotification] = useState<string | null>(null);

  const fetchEvidenceFiles = async () => {
    setIsLoading(true);
    setError(null);

    // 1. Try Electron fs IPC bridge if running in Desktop Electron environment
    if (typeof window !== 'undefined' && (window as any).electronAPI?.listEvidenceFiles) {
      try {
        const result = await (window as any).electronAPI.listEvidenceFiles();
        if (result && result.success && Array.isArray(result.files)) {
          const mapped: EvidenceFileItem[] = result.files.map((f: any) => {
            const isPng = f.filename?.toLowerCase().endsWith('.png') || f.filename?.toLowerCase().endsWith('.jpg');
            const isEV = f.filename?.includes('EV-013') || f.filename?.includes('PROOF') || f.filename?.includes('EV-');
            return {
              filename: f.filename,
              fullPath: f.fullPath,
              sizeBytes: f.sizeBytes || 0,
              mtime: f.mtime || new Date().toISOString(),
              type: isEV || isPng ? 'screenshot_proof' : 'other',
              evidenceId: 'EV-013',
              isEV013: isEV
            };
          });
          setEvidenceFiles(mapped);
          setIsLoading(false);
          return;
        }
      } catch (electronErr) {
        console.warn('Electron fs listing failed, falling back to server API:', electronErr);
      }
    }

    // 2. Fallback to /api/evidence/list (Express server using Node fs module)
    try {
      const res = await fetch('/api/evidence/list');
      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to read reports/evidence`);
      const data = await res.json();
      if (data && data.success && Array.isArray(data.evidenceFiles)) {
        setEvidenceFiles(data.evidenceFiles);
      } else {
        setEvidenceFiles([]);
      }
    } catch (err: any) {
      console.error('Error fetching evidence list:', err);
      setError(err?.message || 'Failed to list reports/evidence folder');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchEvidenceFiles();
  }, []);

  // Filter evidence files
  const filteredFiles = useMemo(() => {
    return evidenceFiles.filter((item) => {
      const isEV = item.evidenceId === 'EV-013' || item.filename.includes('EV-013') || item.filename.includes('PROOF');
      const isImg = item.type === 'screenshot_proof' || item.filename.toLowerCase().endsWith('.png') || item.filename.toLowerCase().endsWith('.jpg');
      const isReport = item.type === 'html_report' || item.type === 'json_report' || item.filename.endsWith('.html') || item.filename.endsWith('.json');

      if (selectedFilter === 'EV013' && !isEV) return false;
      if (selectedFilter === 'SCREENSHOTS' && !isImg) return false;
      if (selectedFilter === 'REPORTS' && !isReport) return false;

      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesName = item.filename.toLowerCase().includes(q);
        const matchesId = item.evidenceId?.toLowerCase().includes(q);
        return matchesName || matchesId;
      }
      return true;
    });
  }, [evidenceFiles, selectedFilter, searchQuery]);

  const ev013Count = useMemo(() => {
    return evidenceFiles.filter(f => f.filename.includes('EV-013') || f.filename.includes('PROOF') || f.evidenceId === 'EV-013').length;
  }, [evidenceFiles]);

  const handleCopyPath = (filename: string) => {
    const fullPath = `reports/evidence/${filename}`;
    navigator.clipboard.writeText(fullPath);
    setCopiedNotification(`Copied path: ${fullPath}`);
    setTimeout(() => setCopiedNotification(null), 3000);
  };

  return (
    <div className="space-y-6">
      {/* Toast Notification */}
      {copiedNotification && (
        <div className="fixed bottom-6 right-6 z-50 bg-emerald-600 text-white px-4 py-2.5 rounded-xl shadow-2xl text-xs font-semibold flex items-center space-x-2 animate-in fade-in duration-200">
          <CheckCircle2 className="w-4 h-4" />
          <span>{copiedNotification}</span>
        </div>
      )}

      {/* Header Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center space-x-3.5">
            <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 rounded-xl">
              <ImageIcon className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-base font-extrabold text-slate-100 tracking-tight">Objective Evidence Gallery</h2>
                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-mono font-bold bg-emerald-950 text-emerald-300 border border-emerald-800">
                  {ev013Count} EV-013 Captures
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Physical captures read from <code className="text-indigo-300 font-mono">reports/evidence/</code> on local filesystem
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2.5 flex-wrap gap-y-2">
            <button
              onClick={fetchEvidenceFiles}
              disabled={isLoading}
              className="flex items-center space-x-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg text-xs font-semibold transition cursor-pointer"
              title="Rescan reports/evidence directory using fs"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
              <span>Rescan Folder</span>
            </button>
            {onExportZip && (
              <button
                onClick={onExportZip}
                disabled={isExportingZip}
                className="flex items-center space-x-1.5 px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold shadow-lg shadow-indigo-600/30 transition cursor-pointer"
                title="Download all proof screenshots in ZIP bundle"
              >
                <Download className="w-3.5 h-3.5" />
                <span>{isExportingZip ? 'Assembling ZIP...' : 'Export All Evidence (ZIP)'}</span>
              </button>
            )}
          </div>
        </div>

        {/* Directory Diagnostic Bar */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-2 border-t border-slate-800/80 text-xs">
          <div className="bg-slate-950/70 p-2.5 rounded-lg border border-slate-800/80 flex items-center space-x-2.5">
            <FolderOpen className="w-4 h-4 text-indigo-400 shrink-0" />
            <div className="min-w-0">
              <div className="text-[10px] text-slate-500 font-bold uppercase">Folder Target</div>
              <div className="text-xs font-mono text-slate-200 truncate">reports/evidence/</div>
            </div>
          </div>
          <div className="bg-slate-950/70 p-2.5 rounded-lg border border-slate-800/80 flex items-center space-x-2.5">
            <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
            <div className="min-w-0">
              <div className="text-[10px] text-slate-500 font-bold uppercase">Citation Standard</div>
              <div className="text-xs text-slate-200 font-semibold truncate">EV-013 Cross-Layer Verification</div>
            </div>
          </div>
          <div className="bg-slate-950/70 p-2.5 rounded-lg border border-slate-800/80 flex items-center space-x-2.5">
            <HardDrive className="w-4 h-4 text-cyan-400 shrink-0" />
            <div className="min-w-0">
              <div className="text-[10px] text-slate-500 font-bold uppercase">Total Files Staged</div>
              <div className="text-xs font-mono text-slate-200 truncate">{evidenceFiles.length} files discovered</div>
            </div>
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          {/* Search Box */}
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search evidence files by filename, EV-013, timestamp..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 text-slate-200 text-xs rounded-lg pl-9 pr-3 py-2 focus:outline-none focus:border-indigo-500 transition placeholder:text-slate-500"
            />
          </div>

          {/* Filter Pills */}
          <div className="flex items-center bg-slate-950 border border-slate-800 rounded-lg p-0.5 text-xs">
            <button
              onClick={() => setSelectedFilter('EV013')}
              className={`px-3 py-1.5 rounded-md text-[11px] font-semibold transition ${
                selectedFilter === 'EV013' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              EV-013 Proofs ({ev013Count})
            </button>
            <button
              onClick={() => setSelectedFilter('SCREENSHOTS')}
              className={`px-3 py-1.5 rounded-md text-[11px] font-semibold transition ${
                selectedFilter === 'SCREENSHOTS' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              All Screenshots
            </button>
            <button
              onClick={() => setSelectedFilter('REPORTS')}
              className={`px-3 py-1.5 rounded-md text-[11px] font-semibold transition ${
                selectedFilter === 'REPORTS' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              HTML/JSON Reports
            </button>
            <button
              onClick={() => setSelectedFilter('ALL')}
              className={`px-3 py-1.5 rounded-md text-[11px] font-semibold transition ${
                selectedFilter === 'ALL' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              All Files ({evidenceFiles.length})
            </button>
          </div>
        </div>

        <div className="flex items-center justify-between text-[11px] text-slate-400">
          <span>
            Showing <strong className="text-slate-200">{filteredFiles.length}</strong> of <strong className="text-slate-200">{evidenceFiles.length}</strong> evidence files
          </span>
          {searchQuery && (
            <button onClick={() => setSearchQuery('')} className="text-indigo-400 hover:text-indigo-300 font-semibold">
              Clear Search
            </button>
          )}
        </div>
      </div>

      {/* Grid of Evidence Cards */}
      {isLoading ? (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-12 text-center space-y-3">
          <RefreshCw className="w-6 h-6 text-indigo-400 animate-spin mx-auto" />
          <p className="text-xs text-slate-300 font-medium">Scanning reports/evidence directory using fs...</p>
        </div>
      ) : error ? (
        <div className="bg-rose-950/20 border border-rose-800/40 rounded-xl p-6 text-center space-y-2">
          <AlertCircle className="w-6 h-6 text-rose-400 mx-auto" />
          <h4 className="text-sm font-bold text-rose-300">Filesystem Scan Notice</h4>
          <p className="text-xs text-rose-400/80 max-w-md mx-auto">{error}</p>
        </div>
      ) : filteredFiles.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-12 text-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-slate-800 flex items-center justify-center mx-auto text-slate-400">
            <ImageIcon className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-bold text-slate-200">No Evidence Captures Found</h3>
          <p className="text-xs text-slate-400 max-w-md mx-auto">
            No files matched your filter. Execute test suites such as <code className="text-indigo-300 font-mono">010_screenshots_sync.py</code> or click <strong className="text-slate-200">Rescan Folder</strong>.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-3 gap-4">
          {filteredFiles.map((file, idx) => {
            const isImage = file.filename.toLowerCase().endsWith('.png') || file.filename.toLowerCase().endsWith('.jpg');
            const fileUrl = `/api/evidence/file/${encodeURIComponent(file.filename)}`;
            const isEV013 = file.filename.includes('EV-013') || file.filename.includes('PROOF') || file.evidenceId === 'EV-013';

            return (
              <div
                key={idx}
                className="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl overflow-hidden shadow-lg transition flex flex-col group"
              >
                {/* Thumbnail / Preview Area */}
                <div className="relative aspect-video bg-slate-950 flex items-center justify-center overflow-hidden border-b border-slate-800/80">
                  {isImage ? (
                    <img
                      src={fileUrl}
                      alt={file.filename}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300 cursor-pointer"
                      onClick={() => setActivePreviewItem(file)}
                      onError={(e) => {
                        (e.target as any).style.display = 'none';
                        (e.target as any).parentElement.innerHTML = `
                          <div class="flex flex-col items-center justify-center p-4 text-center">
                            <span class="text-xs font-mono text-slate-400 font-bold">Screenshot Binary</span>
                            <span class="text-[10px] text-slate-500 mt-1">${file.filename}</span>
                          </div>
                        `;
                      }}
                    />
                  ) : (
                    <div className="p-6 text-center space-y-2">
                      <FileCheck className="w-8 h-8 text-cyan-400 mx-auto" />
                      <div className="text-xs font-mono font-bold text-slate-300 truncate max-w-[200px]">
                        {file.filename}
                      </div>
                    </div>
                  )}

                  {/* Overlay Badges */}
                  <div className="absolute top-2 left-2 flex items-center gap-1.5">
                    {isEV013 && (
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold font-mono bg-indigo-950/90 text-indigo-300 border border-indigo-700/80 shadow-md">
                        EV-013 PROOF
                      </span>
                    )}
                    <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-slate-900/90 text-slate-300 border border-slate-700 shadow-md">
                      {(file.sizeBytes / 1024).toFixed(1)} KB
                    </span>
                  </div>

                  {isImage && (
                    <button
                      onClick={() => setActivePreviewItem(file)}
                      className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white space-x-1.5 cursor-pointer backdrop-blur-[2px]"
                      title="Inspect full resolution capture"
                    >
                      <Maximize2 className="w-5 h-5" />
                      <span className="text-xs font-bold">Inspect Evidence</span>
                    </button>
                  )}
                </div>

                {/* Card Content & Metadata */}
                <div className="p-3.5 flex-1 flex flex-col justify-between space-y-3">
                  <div className="space-y-1">
                    <div className="flex items-center justify-between">
                      <div className="text-xs font-mono font-bold text-slate-200 truncate" title={file.filename}>
                        {file.filename}
                      </div>
                    </div>
                    <div className="text-[11px] text-slate-400 flex items-center space-x-1.5">
                      <Calendar className="w-3 h-3 text-slate-500 shrink-0" />
                      <span>{new Date(file.mtime).toLocaleString()}</span>
                    </div>
                  </div>

                  {/* Action Bar */}
                  <div className="flex items-center justify-between pt-2 border-t border-slate-800/80 gap-2">
                    <button
                      onClick={() => handleCopyPath(file.filename)}
                      className="text-[11px] text-slate-400 hover:text-slate-200 transition font-medium flex items-center space-x-1 cursor-pointer"
                      title="Copy relative file path"
                    >
                      <span>Copy Path</span>
                    </button>

                    <div className="flex items-center space-x-1.5">
                      {isImage && (
                        <button
                          onClick={() => setActivePreviewItem(file)}
                          className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-[11px] font-semibold transition cursor-pointer flex items-center space-x-1"
                        >
                          <Eye className="w-3 h-3" />
                          <span>View</span>
                        </button>
                      )}
                      <a
                        href={fileUrl}
                        download={file.filename}
                        target="_blank"
                        rel="noreferrer"
                        className="px-2.5 py-1 bg-indigo-600/90 hover:bg-indigo-600 text-white rounded text-[11px] font-semibold transition cursor-pointer flex items-center space-x-1"
                        title="Download raw capture file"
                      >
                        <Download className="w-3 h-3" />
                        <span>Download</span>
                      </a>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Full Resolution Modal Preview */}
      {activePreviewItem && (
        <div
          className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setActivePreviewItem(null)}
        >
          <div
            className="bg-slate-900 border border-slate-700 rounded-2xl max-w-5xl w-full max-h-[90vh] flex flex-col overflow-hidden shadow-2xl animate-in zoom-in-95 duration-150"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="p-4 bg-slate-950 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center space-x-2.5">
                <div className="p-1.5 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 rounded-lg">
                  <ImageIcon className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-xs font-mono font-bold text-slate-100">{activePreviewItem.filename}</h3>
                  <p className="text-[10px] text-slate-400">
                    Captured: {new Date(activePreviewItem.mtime).toLocaleString()} &bull; Size: {(activePreviewItem.sizeBytes / 1024).toFixed(1)} KB
                  </p>
                </div>
              </div>

              <div className="flex items-center space-x-2">
                <a
                  href={`/api/evidence/file/${encodeURIComponent(activePreviewItem.filename)}`}
                  download={activePreviewItem.filename}
                  className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg flex items-center space-x-1.5 transition"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download Original</span>
                </a>
                <button
                  onClick={() => setActivePreviewItem(null)}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg transition"
                >
                  Close
                </button>
              </div>
            </div>

            {/* Modal Image Display */}
            <div className="p-4 bg-slate-950 flex-1 overflow-auto flex items-center justify-center min-h-[400px]">
              <img
                src={`/api/evidence/file/${encodeURIComponent(activePreviewItem.filename)}`}
                alt={activePreviewItem.filename}
                className="max-w-full max-h-[70vh] object-contain rounded-lg border border-slate-800 shadow-2xl"
              />
            </div>

            {/* Modal Footer */}
            <div className="p-3 bg-slate-900 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
              <div className="font-mono text-[11px] text-slate-400">
                Location: <span className="text-indigo-300">reports/evidence/{activePreviewItem.filename}</span>
              </div>
              <button
                onClick={() => handleCopyPath(activePreviewItem.filename)}
                className="text-indigo-400 hover:text-indigo-300 font-semibold"
              >
                Copy Path
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
