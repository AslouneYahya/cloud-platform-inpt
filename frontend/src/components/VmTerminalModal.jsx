import React, { useState, useEffect, useRef } from 'react';
import { executeVmCommand } from '../api/vms.js';

export default function VmTerminalModal({ vm, onClose }) {
  const [lines, setLines] = useState([]);
  const [currentInput, setCurrentInput] = useState('');
  const [isExecuting, setIsExecuting] = useState(false);
  const [cmdHistory, setCmdHistory] = useState([]);
  const [historyIdx, setHistoryIdx] = useState(-1);

  const terminalEndRef = useRef(null);
  const inputRef = useRef(null);

  const ip = vm.ipAddress || '192.168.60.231';
  const prompt = `root@${vm.name}:~# `;

  // Realistic SSH login banner on connect
  useEffect(() => {
    const banner = [
      `Connecting to ${ip}:22...`,
      `Connection established. Authenticated to ${vm.name} as 'root'.`,
      ``,
      `Welcome to ${vm.os} (Linux 5.15.0-1040-raspi aarch64)`,
      ` * System information: ${vm.cpu} vCPU, ${vm.ramMb}MB RAM, ${vm.diskGb}GB Disk`,
      ` * Cluster Node:       ${vm.nodeId || 'rpi-master'}`,
      ` * IPv4 Address:       ${ip}`,
      ``,
      `Last login: ${new Date().toUTCString()} from 192.168.1.100`,
      ``
    ];
    setLines(banner);
    if (inputRef.current) {
      inputRef.current.focus();
    }
  }, [vm]);

  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [lines, isExecuting]);

  function focusTerminal() {
    if (inputRef.current) {
      inputRef.current.focus();
    }
  }

  async function handleKeyDown(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      const cmd = currentInput.trim();

      if (!cmd) {
        setLines(prev => [...prev, prompt]);
        setCurrentInput('');
        return;
      }

      if (cmd === 'clear') {
        setLines([]);
        setCurrentInput('');
        return;
      }

      if (cmd === 'exit') {
        onClose();
        return;
      }

      // Add to display and command history
      const fullCmdLine = `${prompt}${cmd}`;
      setLines(prev => [...prev, fullCmdLine]);
      setCmdHistory(prev => [cmd, ...prev]);
      setHistoryIdx(-1);
      setCurrentInput('');
      setIsExecuting(true);

      try {
        const res = await executeVmCommand(vm.id, cmd);
        const data = res.data?.data || res.data || {};
        const output = data.stdout || data.stderr || '';
        if (output) {
          // split lines to preserve raw terminal output format
          const outputLines = output.split('\n');
          // remove last empty line if any
          if (outputLines[outputLines.length - 1] === '') outputLines.pop();
          setLines(prev => [...prev, ...outputLines]);
        }
      } catch (err) {
        const errMsg = err?.response?.data?.message || err.message || 'Execution error';
        setLines(prev => [...prev, `bash: ${errMsg}`]);
      } finally {
        setIsExecuting(false);
        setTimeout(focusTerminal, 20);
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (cmdHistory.length > 0 && historyIdx < cmdHistory.length - 1) {
        const next = historyIdx + 1;
        setHistoryIdx(next);
        setCurrentInput(cmdHistory[next]);
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (historyIdx > 0) {
        const next = historyIdx - 1;
        setHistoryIdx(next);
        setCurrentInput(cmdHistory[next]);
      } else if (historyIdx === 0) {
        setHistoryIdx(-1);
        setCurrentInput('');
      }
    }
  }

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(3px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 2000,
        padding: '1.5rem'
      }}
    >
      {/* Terminal Window */}
      <div
        onClick={e => {
          e.stopPropagation();
          focusTerminal();
        }}
        style={{
          width: '100%',
          maxWidth: '900px',
          height: '80vh',
          backgroundColor: '#0a0a0a',
          color: '#d4d4d4',
          borderRadius: '8px',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 20px 60px rgba(0, 0, 0, 0.8)',
          border: '1px solid #2d2d2d',
          overflow: 'hidden',
          fontFamily: 'Consolas, Monaco, "Courier New", monospace'
        }}
      >
        {/* Title Bar */}
        <div
          style={{
            backgroundColor: '#181818',
            padding: '0.5rem 0.85rem',
            borderBottom: '1px solid #262626',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            userSelect: 'none'
          }}
        >
          {/* Terminal Dots */}
          <div style={{ display: 'flex', gap: '7px', alignItems: 'center' }}>
            <span
              onClick={onClose}
              title="Fermer la session"
              style={{
                width: '12px',
                height: '12px',
                borderRadius: '50%',
                backgroundColor: '#ff5f56',
                display: 'inline-block',
                cursor: 'pointer'
              }}
            />
            <span
              style={{
                width: '12px',
                height: '12px',
                borderRadius: '50%',
                backgroundColor: '#ffbd2e',
                display: 'inline-block'
              }}
            />
            <span
              style={{
                width: '12px',
                height: '12px',
                borderRadius: '50%',
                backgroundColor: '#27c93f',
                display: 'inline-block'
              }}
            />
          </div>

          {/* Window Title */}
          <div style={{ fontSize: '0.8rem', color: '#888', fontWeight: '500' }}>
            root@{ip} — ssh {vm.name}
          </div>

          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: '#666',
              fontSize: '1rem',
              cursor: 'pointer',
              padding: '0 0.25rem'
            }}
          >
            ✕
          </button>
        </div>

        {/* Terminal Screen Body */}
        <div
          style={{
            flex: 1,
            padding: '1rem 1.25rem',
            overflowY: 'auto',
            fontSize: '0.86rem',
            lineHeight: '1.45',
            cursor: 'text'
          }}
        >
          {lines.map((l, i) => (
            <div
              key={i}
              style={{
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
                color: l.startsWith(prompt) ? '#fff' : '#b0b0b0',
                marginBottom: '1px'
              }}
            >
              {l.startsWith(prompt) ? (
                <>
                  <span style={{ color: '#4ade80', fontWeight: 'bold' }}>{prompt}</span>
                  <span>{l.slice(prompt.length)}</span>
                </>
              ) : (
                l
              )}
            </div>
          ))}

          {/* Active input line with blinking cursor */}
          <div style={{ display: 'flex', alignItems: 'center', marginTop: '2px' }}>
            <span style={{ color: '#4ade80', fontWeight: 'bold', userSelect: 'none' }}>
              {prompt}
            </span>
            <input
              ref={inputRef}
              type="text"
              value={currentInput}
              onChange={e => setCurrentInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isExecuting}
              autoFocus
              spellCheck={false}
              autoComplete="off"
              style={{
                flex: 1,
                backgroundColor: 'transparent',
                color: '#fff',
                border: 'none',
                outline: 'none',
                fontFamily: 'inherit',
                fontSize: 'inherit',
                padding: 0,
                marginLeft: '4px'
              }}
            />
          </div>

          {isExecuting && (
            <div style={{ color: '#888', fontStyle: 'italic', marginTop: '4px' }}>
              [executing...]
            </div>
          )}

          <div ref={terminalEndRef} />
        </div>
      </div>
    </div>
  );
}
