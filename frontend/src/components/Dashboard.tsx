'use client';
import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';

interface DashboardProps {
  data: {
    session_id: string;
    total_entities: number;
    risk_level: string;
    risk_score: number;
    entities: any[];
    risk_factors: any[];
    summary: string;
    masked_text: string;
  };
}

export default function Dashboard({ data }: DashboardProps) {
  const [activeTab, setActiveTab] = useState('entities');
  const [chatInput, setChatInput] = useState('');
  const [chatHistory, setChatHistory] = useState<{role: string, content: string}[]>([]);
  const [isChatting, setIsChatting] = useState(false);

  const getRiskClass = (level: string) => {
    if (level === 'HIGH') return 'risk-high';
    if (level === 'MEDIUM') return 'risk-medium';
    return 'risk-low';
  };

  const handleChat = async () => {
    if (!chatInput.trim()) return;
    
    const newHistory = [...chatHistory, { role: 'user', content: chatInput }];
    setChatHistory(newHistory);
    setChatInput('');
    setIsChatting(true);

    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const res = await fetch(`${apiUrl}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: data.session_id, message: chatInput })
      });
      
      const responseData = await res.json();
      setChatHistory([...newHistory, { role: 'assistant', content: responseData.reply || 'No response.' }]);
    } catch (e) {
      setChatHistory([...newHistory, { role: 'assistant', content: '⚠️ Error connecting to server.' }]);
    } finally {
      setIsChatting(false);
    }
  };

  const handleDownloadCsv = () => {
    if (!data.entities || data.entities.length === 0) return;
    const headers = ['Type', 'Masked Value', 'Method', 'Confidence', 'Line'];
    const rows = data.entities.map(e => [
      e.type, 
      `"${e.masked_value}"`, 
      e.method, 
      e.confidence, 
      e.line || 'N/A'
    ]);
    const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'sensitive_entities.csv';
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadTxt = () => {
    if (!data.masked_text) return;
    const blob = new Blob([data.masked_text], { type: 'text/plain;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'redacted_document.txt';
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="animate-fade-in space-y-6">
      {/* Top Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="glass-card p-6 flex flex-col items-center justify-center">
          <span className="text-gray-400 text-sm font-semibold uppercase tracking-wider mb-2">Total Entities</span>
          <span className="text-4xl font-bold">{data.total_entities}</span>
        </div>
        <div className="glass-card p-6 flex flex-col items-center justify-center">
          <span className="text-gray-400 text-sm font-semibold uppercase tracking-wider mb-2">Risk Level</span>
          <span className={`text-3xl font-bold ${getRiskClass(data.risk_level)}`}>{data.risk_level}</span>
        </div>
        <div className="glass-card p-6 flex flex-col items-center justify-center">
          <span className="text-gray-400 text-sm font-semibold uppercase tracking-wider mb-2">Risk Score</span>
          <span className="text-4xl font-bold">{data.risk_score.toFixed(0)}</span>
        </div>
        <div className="glass-card p-6 flex flex-col items-center justify-center">
          <span className="text-gray-400 text-sm font-semibold uppercase tracking-wider mb-2">Session ID</span>
          <span className="text-sm font-mono text-gray-300 break-all">{data.session_id.split('-')[0]}...</span>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="glass-panel overflow-hidden">
        {/* Tabs and Actions */}
        <div className="flex border-b border-white/10 items-center justify-between flex-wrap gap-4 p-2 sm:p-0">
          <div className="flex">
            {['entities', 'summary', 'chat'].map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-6 py-4 text-center font-medium transition-colors ${activeTab === tab ? 'bg-white/10 text-white border-b-2 border-blue-500' : 'text-gray-400 hover:bg-white/5'}`}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>
          <div className="flex gap-2 sm:pr-4">
            <button onClick={handleDownloadCsv} className="text-sm glow-button px-4 py-2" title="Export Detected Entities">
              ⬇️ CSV
            </button>
            <button onClick={handleDownloadTxt} className="text-sm glow-button px-4 py-2" title="Download Fully Redacted Document Text">
              ⬇️ Redacted TXT
            </button>
          </div>
        </div>

        {/* Tab Content */}
        <div className="p-6">
          {activeTab === 'entities' && (
            <div className="space-y-4 animate-fade-in">
              <h3 className="text-xl font-semibold mb-4">Detected Sensitive Data</h3>
              {data.entities.length === 0 ? (
                <div className="text-center py-10 text-gray-400">No sensitive entities detected.</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-white/10 text-gray-400">
                        <th className="p-3">Type</th>
                        <th className="p-3">Masked Value</th>
                        <th className="p-3">Method</th>
                        <th className="p-3">Confidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.entities.map((e, i) => (
                        <tr key={i} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                          <td className="p-3 font-medium">{e.type.replace('_', ' ').toUpperCase()}</td>
                          <td className="p-3 font-mono text-sm">{e.masked_value}</td>
                          <td className="p-3 text-sm text-gray-400 uppercase">{e.method}</td>
                          <td className="p-3 text-sm">{(e.confidence * 100).toFixed(0)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {activeTab === 'summary' && (
            <div className="prose prose-invert max-w-none animate-fade-in bg-black/20 p-6 rounded-lg">
              <ReactMarkdown>{data.summary}</ReactMarkdown>
            </div>
          )}

          {activeTab === 'chat' && (
            <div className="flex flex-col h-[500px] animate-fade-in">
              <div className="flex-1 overflow-y-auto space-y-4 p-4 mb-4 border border-white/10 rounded-lg bg-black/20">
                {chatHistory.length === 0 ? (
                  <div className="text-center text-gray-400 mt-20">
                    <p>Ask questions about your uploaded documents.</p>
                    <p className="text-sm">e.g., "What is the compliance risk here?"</p>
                  </div>
                ) : (
                  chatHistory.map((msg, i) => (
                    <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[80%] p-4 rounded-xl ${msg.role === 'user' ? 'bg-blue-600/50 rounded-br-none' : 'glass-card rounded-bl-none'}`}>
                        <div className="prose prose-sm prose-invert">
                          <ReactMarkdown>{msg.content}</ReactMarkdown>
                        </div>
                      </div>
                    </div>
                  ))
                )}
                {isChatting && (
                  <div className="flex justify-start">
                    <div className="glass-card p-4 rounded-xl rounded-bl-none animate-pulse text-gray-400">
                      Thinking...
                    </div>
                  </div>
                )}
              </div>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={chatInput}
                  onChange={e => setChatInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleChat()}
                  placeholder="Ask a question..."
                  className="flex-1 bg-white/5 border border-white/10 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-500 text-white"
                />
                <button
                  onClick={handleChat}
                  disabled={isChatting || !chatInput.trim()}
                  className="glow-button px-6 py-3"
                >
                  Send
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
