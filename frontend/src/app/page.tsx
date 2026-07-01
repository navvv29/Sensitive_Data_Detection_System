'use client';
import { useState } from 'react';
import Dashboard from '@/components/Dashboard';

export default function Home() {
  const [files, setFiles] = useState<File[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles(Array.from(e.target.files));
      setResult(null);
      setError('');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (files.length === 0) return;
    
    setIsProcessing(true);
    setError('');
    
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));
    formData.append('enable_nlp', 'true');
    formData.append('use_llm', 'true');
    formData.append('llm_provider', 'groq');

    try {
      const res = await fetch('http://localhost:8000/api/upload', {
        method: 'POST',
        body: formData,
      });
      
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Failed to process documents');
      }
      
      const data = await res.json();
      setResult(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <main className="min-h-screen p-8 max-w-7xl mx-auto">
      <header className="mb-12 text-center animate-fade-in">
        <h1 className="text-5xl font-bold mb-4 bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500">
          Sensitive Data Detection
        </h1>
        <p className="text-xl text-gray-400">Secure. Compliant. Intelligent.</p>
      </header>

      {!result ? (
        <div className="max-w-xl mx-auto glass-panel p-8 animate-fade-in">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="border-2 border-dashed border-white/20 rounded-xl p-10 text-center hover:border-blue-400/50 transition-colors bg-white/5 cursor-pointer relative">
              <input 
                type="file" 
                multiple 
                onChange={handleFileChange}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                accept=".pdf,.txt,.csv"
              />
              <div className="pointer-events-none">
                <div className="text-4xl mb-4">📄</div>
                <h3 className="text-lg font-semibold mb-2">Drag & Drop Documents</h3>
                <p className="text-sm text-gray-400">Supports PDF, TXT, CSV</p>
                {files.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-white/10 text-blue-400 font-medium">
                    {files.length} file(s) selected
                  </div>
                )}
              </div>
            </div>

            {error && (
              <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-4 rounded-lg text-sm">
                ⚠️ {error}
              </div>
            )}

            <button 
              type="submit" 
              disabled={isProcessing || files.length === 0}
              className="w-full glow-button py-4 text-lg flex items-center justify-center gap-2"
            >
              {isProcessing ? (
                <>
                  <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                  Analyzing Documents...
                </>
              ) : (
                'Start Analysis'
              )}
            </button>
          </form>
        </div>
      ) : (
        <div>
          <div className="mb-6 flex justify-between items-center animate-fade-in">
            <h2 className="text-2xl font-semibold">Analysis Results</h2>
            <button 
              onClick={() => { setResult(null); setFiles([]); }}
              className="text-gray-400 hover:text-white transition-colors text-sm underline"
            >
              Start New Analysis
            </button>
          </div>
          <Dashboard data={result} />
        </div>
      )}
    </main>
  );
}
