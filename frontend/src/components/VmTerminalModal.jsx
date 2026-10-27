import React, { useState, useEffect, useRef } from 'react';
import { executeVmCommand } from '../api/vms.js';

export default function VmTerminalModal({ vm, onClose }) {
  const [activeTab, setActiveTab] = useState('terminal'); // 'terminal' | 'instructions'
  const [command, setCommand] = useState('');
  const [executing, setExecuting] = useState(false);
  const [history, setHistory] = useState([]);
  const [cmdHistory, setCmdHistory] = useState([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [copied, setCopied] = useState(false);

  const inputRef = useRef(null);
  const terminalEndRef = useRef(null);

  const ip = vm.ipAddress || '192.168.60.231';
  const sshUser = 'root';
  const sshCommand = `ssh ${sshUser}@${ip}`;

  // Initial welcome MOTD banner
  useEffect(() => {
    const motd = `
================================================================================
  INPT CLOUD PLATFORM — WEB SSH INSTANCE CONNECT
  Cluster Node : ${vm.nodeId || 'rpi-master'} (Raspberry Pi 4 ARM64)
  Instance     : ${vm.name} (${vm.os})
  IP Address   : ${ip} | Port: 22 (SSH)
  Connected at : ${new Date().toLocaleString()}
================================================================================
Type 'help' for available shortcuts, or enter any Linux shell command.
`;
    setHistory([{ type: 'banner', content: motd }]);
    if (inputRef.current) inputRef.current.focus();
  }, [vm]);

  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [history]);

  async function runCommand(cmdToRun) {
    const rawCmd = (cmdToRun !== undefined ? cmdToRun : command).trim();
    if (!rawCmd) return;

    if (rawCmd === 'clear') {
      setHistory([]);
      setCommand('');
      return;
    }

    if (rawCmd === 'help') {
      const helpText = `Available Quick Commands:
  • uptime            - Show system uptime and load average
  • free -m           - Display RAM usage in megabytes
  • df -h             - Display disk filesystem storage
  • ip a              - Show network IP and interfaces
  • uname -a          - Show Linux kernel version & architecture
  • cat /etc/os-release - Display OS distribution info
  • clear             - Clear terminal screen
`;
      setHistory(prev => [
        ...prev,
        { type: 'cmd', cmd: rawCmd },
        { type: 'output', content: helpText, success: true }
      ]);
      setCommand('');
      return;
    }

    setExecuting(true);
    setCmdHistory(prev => [rawCmd, ...prev]);
    setHistoryIndex(-1);

    // Append command to display
    setHistory(prev => [...prev, { type: 'cmd', cmd: rawCmd }]);
    setCommand('');

    try {
      const res = await executeVmCommand(vm.id, rawCmd);
      const data = res.data?.data || res.data || {};
      const output = data.stdout || data.stderr || 'Command executed with no output.';
      setHistory(prev => [
        ...prev,
        {
          type: 'output',
          content: output,
          success: data.exitCode === 0,
          error: data.stderr && data.exitCode !== 0
        }
      ]);
    } catch (err) {
      const errMsg = err?.response?.data?.message || err.message || 'Execution error';
      setHistory(prev => [
        ...prev,
        { type: 'output', content: `Error: ${errMsg}`, success: false, error: true }
      ]);
    } finally {
      setExecuting(false);
      setTimeout(() => {
        if (inputRef.current) inputRef.current.focus();
      }, 50);
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      runCommand();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (cmdHistory.length > 0 && historyIndex < cmdHistory.length - 1) {
        const nextIdx = historyIndex + 1;
        setHistoryIndex(nextIdx);
        setCommand(cmdHistory[nextIdx]);
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (historyIndex > 0) {
        const nextIdx = historyIndex - 1;
        setHistoryIndex(nextIdx);
        setCommand(cmdHistory[nextIdx]);
      } else if (historyIndex === 0) {
        setHistoryIndex(-1);
        setCommand('');
      }
    }
  }

  function handleCopySsh() {
    navigator.clipboard.writeText(sshCommand);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(15, 23, 42, 0.8)',
      backdropFilter: 'blur(4px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 2000,
      padding: '1rem'
    }}>
      <div style={{
        backgroundColor: '#030712',
        color: '#f9fafb',
        borderRadius: '14px',
        width: '100%',
        maxWidth: '920px',
        height: '82vh',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.6)',
        border: '1px solid #1f2937',
        overflow: 'hidden'
      }}>
        {/* Terminal Header */}
        <div style={{
          backgroundColor: '#111827',
          padding: '0.85rem 1.25rem',
          borderBottom: '1px solid #1f2937',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '0.5rem'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div style={{
              width: '10px',
              height: '10px',
              borderRadius: '50%',
              backgroundColor: '#10b981',
              boxShadow: '0 0 10px #10b981'
            }}></div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <strong style={{ fontSize: '0.95rem', color: '#f3f4f6' }}>
                  Web SSH Console — {vm.name}
                </strong>
                <span style={{
                  backgroundColor: 'rgba(16, 185, 129, 0.15)',
                  color: '#34d399',
                  border: '1px solid rgba(16, 185, 129, 0.3)',
                  padding: '0.1rem 0.5rem',
                  borderRadius: '10px',
                  fontSize: '0.72rem',
                  fontWeight: '700'
                }}>
                  SESSION ACTIVE
                </span>
              </div>
              <div style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: '0.15rem' }}>
                Cible : <code style={{ color: '#60a5fa' }}>{sshUser}@{ip}:22</code> • Nœud : {vm.nodeId || 'rpi-master'}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <div style={{ display: 'flex', backgroundColor: '#1f2937', borderRadius: '6px', padding: '2px' }}>
              <button
                onClick={() => setActiveTab('terminal')}
                style={{
                  backgroundColor: activeTab === 'terminal' ? '#374151' : 'transparent',
                  color: activeTab === 'terminal' ? '#fff' : '#9ca3af',
                  border: 'none',
                  borderRadius: '4px',
                  padding: '0.3rem 0.65rem',
                  fontSize: '0.75rem',
                  cursor: 'pointer',
                  fontWeight: '600'
                }}
              >
                🖥 Console Web
              </button>
              <button
                onClick={() => setActiveTab('instructions')}
                style={{
                  backgroundColor: activeTab === 'instructions' ? '#374151' : 'transparent',
                  color: activeTab === 'instructions' ? '#fff' : '#9ca3af',
                  border: 'none',
                  borderRadius: '4px',
                  padding: '0.3rem 0.65rem',
                  fontSize: '0.75rem',
                  cursor: 'pointer',
                  fontWeight: '600'
                }}
              >
                🔑 Client SSH
              </button>
            </div>
            <button
              onClick={onClose}
              style={{
                backgroundColor: 'transparent',
                color: '#9ca3af',
                border: 'none',
                fontSize: '1.25rem',
                cursor: 'pointer',
                padding: '0.2rem 0.5rem'
              }}
            >
              ✕
            </button>
          </div>
        </div>

        {activeTab === 'terminal' ? (
          <>
            {/* Quick action chips */}
            <div style={{
              backgroundColor: '#0a0f1d',
              padding: '0.45rem 1.25rem',
              borderBottom: '1px solid #1f2937',
              display: 'flex',
              gap: '0.4rem',
              flexWrap: 'wrap',
              alignItems: 'center'
            }}>
              <span style={{ fontSize: '0.72rem', color: '#6b7280', marginRight: '0.25rem' }}>
                Raccourcis :
              </span>
              {[
                { label: '📊 Uptime', cmd: 'uptime' },
                { label: '🧠 RAM', cmd: 'free -m' },
                { label: '💾 Disque', cmd: 'df -h' },
                { label: '🌐 Réseau', cmd: 'ip a' },
                { label: '🐧 Kernel', cmd: 'uname -a' },
                { label: 'ℹ Système', cmd: 'cat /etc/os-release' },
                { label: '🧹 Clear', cmd: 'clear' }
              ].map(item => (
                <button
                  key={item.label}
                  onClick={() => runCommand(item.cmd)}
                  disabled={executing}
                  style={{
                    backgroundColor: '#1f2937',
                    color: '#d1d5db',
                    border: '1px solid #374151',
                    borderRadius: '4px',
                    padding: '0.2rem 0.5rem',
                    fontSize: '0.72rem',
                    cursor: executing ? 'wait' : 'pointer'
                  }}
                >
                  {item.label}
                </button>
              ))}
            </div>

            {/* Terminal Body */}
            <div style={{
              flex: 1,
              padding: '1.25rem',
              overflowY: 'auto',
              fontFamily: 'Consolas, Monaco, "Lucida Console", "Liberation Mono", monospace',
              fontSize: '0.84rem',
              lineHeight: '1.5',
              backgroundColor: '#030712'
            }}>
              {history.map((item, index) => {
                if (item.type === 'banner') {
                  return (
                    <pre key={index} style={{ margin: '0 0 1rem 0', color: '#60a5fa', whiteSpace: 'pre-wrap', fontSize: '0.78rem' }}>
                      {item.content}
                    </pre>
                  );
                }
                if (item.type === 'cmd') {
                  return (
                    <div key={index} style={{ color: '#f3f4f6', marginTop: '0.5rem', display: 'flex', gap: '0.4rem' }}>
                      <span style={{ color: '#10b981', fontWeight: 'bold' }}>
                        root@{vm.name}:~#
                      </span>
                      <span>{item.cmd}</span>
                    </div>
                  );
                }
                if (item.type === 'output') {
                  return (
                    <pre
                      key={index}
                      style={{
                        margin: '0.25rem 0 0.5rem 0',
                        color: item.error ? '#f87171' : '#d1d5db',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                        fontSize: '0.82rem'
                      }}
                    >
                      {item.content}
                    </pre>
                  );
                }
                return null;
              })}

              {executing && (
                <div style={{ color: '#fbbf24', marginTop: '0.35rem', display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.78rem' }}>
                  <span>⏳ Exécution de la commande sur le Raspberry Pi...</span>
                </div>
              )}

              <div ref={terminalEndRef} />
            </div>

            {/* Terminal Input Bar */}
            <div style={{
              backgroundColor: '#111827',
              padding: '0.75rem 1.25rem',
              borderTop: '1px solid #1f2937',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem'
            }}>
              <span style={{
                color: '#10b981',
                fontWeight: 'bold',
                fontFamily: 'monospace',
                fontSize: '0.88rem',
                userSelect: 'none'
              }}>
                root@{vm.name}:~#
              </span>
              <input
                ref={inputRef}
                type="text"
                value={command}
                onChange={e => setCommand(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={executing}
                placeholder="Entrez une commande (ex: df -h, uptime, ls -la)..."
                style={{
                  flex: 1,
                  backgroundColor: '#030712',
                  color: '#f9fafb',
                  border: '1px solid #374151',
                  borderRadius: '6px',
                  padding: '0.5rem 0.75rem',
                  fontFamily: 'monospace',
                  fontSize: '0.86rem',
                  outline: 'none'
                }}
              />
              <button
                onClick={() => runCommand()}
                disabled={executing || !command.trim()}
                style={{
                  backgroundColor: '#2563eb',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '6px',
                  padding: '0.5rem 1rem',
                  fontSize: '0.82rem',
                  fontWeight: '600',
                  cursor: executing || !command.trim() ? 'not-allowed' : 'pointer',
                  opacity: executing || !command.trim() ? 0.6 : 1
                }}
              >
                {executing ? '...' : 'Envoyer ↵'}
              </button>
            </div>
          </>
        ) : (
          /* Client SSH Instructions Tab */
          <div style={{ padding: '2rem', overflowY: 'auto', backgroundColor: '#0b1120', flex: 1 }}>
            <h3 style={{ margin: '0 0 1rem 0', color: '#f3f4f6', fontSize: '1.1rem' }}>
              Connexion directe via votre client SSH local
            </h3>
            <p style={{ color: '#9ca3af', fontSize: '0.85rem', marginBottom: '1.5rem' }}>
              Vous pouvez vous connecter à cette machine virtuelle depuis votre terminal local (PowerShell, Linux, macOS) à l'aide de votre client OpenSSH.
            </p>

            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', fontSize: '0.8rem', color: '#9ca3af', marginBottom: '0.4rem' }}>
                Commande de connexion directe :
              </label>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <input
                  type="text"
                  readOnly
                  value={sshCommand}
                  style={{
                    flex: 1,
                    backgroundColor: '#030712',
                    color: '#34d399',
                    fontFamily: 'monospace',
                    padding: '0.65rem 0.85rem',
                    border: '1px solid #374151',
                    borderRadius: '6px'
                  }}
                />
                <button
                  onClick={handleCopySsh}
                  style={{
                    backgroundColor: copied ? '#10b981' : '#2563eb',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '6px',
                    padding: '0 1.25rem',
                    cursor: 'pointer',
                    fontWeight: '600',
                    fontSize: '0.85rem'
                  }}
                >
                  {copied ? '✓ Copié !' : 'Copier'}
                </button>
              </div>
            </div>

            <div style={{ backgroundColor: '#111827', borderRadius: '8px', padding: '1rem', border: '1px solid #1f2937', fontSize: '0.82rem', color: '#d1d5db' }}>
              <strong style={{ color: '#60a5fa' }}>💡 Configuration OpenSSH recommandée (~/.ssh/config) :</strong>
              <pre style={{ backgroundColor: '#030712', padding: '0.75rem', borderRadius: '6px', color: '#f3f4f6', marginTop: '0.5rem', fontFamily: 'monospace' }}>
{`Host ${vm.name}
    HostName ${ip}
    User root
    Port 22
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null`}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
