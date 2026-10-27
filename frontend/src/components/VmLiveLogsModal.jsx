import React, { useState, useEffect, useRef } from 'react';
import { getVmLogs } from '../api/vms.js';

export default function VmLiveLogsModal({ vm, onClose }) {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [autoScroll, setAutoScroll] = useState(true);
  const [filterLevel, setFilterLevel] = useState('ALL');
  const [lastRefreshed, setLastRefreshed] = useState(new Date());
  const terminalEndRef = useRef(null);

  const isLive = vm.status === 'PROVISIONING' || vm.status === 'PENDING';

  async function fetchLogs() {
    try {
      const res = await getVmLogs(vm.id);
      const data = res.data?.data || res.data || [];
      setLogs(data);
      setLastRefreshed(new Date());
    } catch (err) {
      console.error('Erreur chargement logs:', err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchLogs();

    // Auto-poll logs every 1.5s if VM is in provisioning
    let interval = null;
    if (isLive) {
      interval = setInterval(() => {
        fetchLogs();
      }, 1500);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [vm.id, isLive]);

  useEffect(() => {
    if (autoScroll && terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  function getLevelColor(lvl) {
    switch (lvl?.toUpperCase()) {
      case 'SUCCESS':
        return '#4ade80'; // Emerald green
      case 'WARN':
      case 'WARNING':
        return '#facc15'; // Amber yellow
      case 'ERROR':
        return '#f87171'; // Coral red
      case 'INFO':
      default:
        return '#38bdf8'; // Sky blue
    }
  }

  const filteredLogs = logs.filter(l => {
    if (filterLevel === 'ALL') return true;
    return l.level?.toUpperCase() === filterLevel;
  });

  function downloadLogs() {
    const text = logs
      .map(l => `[${l.timestamp}] [${l.level}] [${l.stage}] ${l.message}`)
      .join('\n');
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `provisioning-${vm.name}-${vm.id.slice(0, 8)}.log`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(15, 23, 42, 0.75)',
      backdropFilter: 'blur(4px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 2000,
      padding: '1rem'
    }}>
      <div style={{
        backgroundColor: '#0b1120',
        color: '#f8fafc',
        borderRadius: '14px',
        width: '100%',
        maxWidth: '860px',
        height: '80vh',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
        border: '1px solid #1e293b',
        overflow: 'hidden'
      }}>
        {/* AWS-style Console Header */}
        <div style={{
          backgroundColor: '#0f172a',
          padding: '0.85rem 1.25rem',
          borderBottom: '1px solid #1e293b',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '0.5rem'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontSize: '1.25rem' }}>☁</span>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <strong style={{ fontSize: '0.95rem', color: '#f1f5f9' }}>
                  Journaux de déploiement en direct (AWS CloudWatch Engine)
                </strong>
                {isLive ? (
                  <span style={{
                    backgroundColor: 'rgba(56, 189, 248, 0.15)',
                    color: '#38bdf8',
                    border: '1px solid rgba(56, 189, 248, 0.3)',
                    padding: '0.15rem 0.5rem',
                    borderRadius: '12px',
                    fontSize: '0.72rem',
                    fontWeight: '700',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.35rem'
                  }}>
                    <span style={{
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      backgroundColor: '#38bdf8',
                      boxShadow: '0 0 8px #38bdf8'
                    }}></span>
                    STREAMING LIVE
                  </span>
                ) : (
                  <span style={{
                    backgroundColor: 'rgba(74, 222, 128, 0.15)',
                    color: '#4ade80',
                    border: '1px solid rgba(74, 222, 128, 0.3)',
                    padding: '0.15rem 0.5rem',
                    borderRadius: '12px',
                    fontSize: '0.72rem',
                    fontWeight: '600'
                  }}>
                    ✓ Provisionné
                  </span>
                )}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.15rem' }}>
                Instance : <strong style={{ color: '#cbd5e1' }}>{vm.name}</strong> • OS : {vm.os} • ID : <code style={{ color: '#38bdf8' }}>{vm.id}</code>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <button
              onClick={downloadLogs}
              title="Exporter les logs (.log)"
              style={{
                backgroundColor: '#1e293b',
                color: '#cbd5e1',
                border: '1px solid #334155',
                padding: '0.35rem 0.75rem',
                borderRadius: '6px',
                fontSize: '0.78rem',
                cursor: 'pointer'
              }}
            >
              📥 Exporter
            </button>
            <button
              onClick={onClose}
              style={{
                backgroundColor: 'transparent',
                color: '#94a3b8',
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

        {/* Toolbar */}
        <div style={{
          backgroundColor: '#090d16',
          padding: '0.5rem 1.25rem',
          borderBottom: '1px solid #1e293b',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '0.78rem',
          color: '#94a3b8'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span>Filtrer par niveau :</span>
            {['ALL', 'INFO', 'SUCCESS', 'WARN', 'ERROR'].map(lvl => (
              <button
                key={lvl}
                onClick={() => setFilterLevel(lvl)}
                style={{
                  backgroundColor: filterLevel === lvl ? '#1e293b' : 'transparent',
                  color: filterLevel === lvl ? '#f8fafc' : '#64748b',
                  border: filterLevel === lvl ? '1px solid #334155' : '1px solid transparent',
                  borderRadius: '4px',
                  padding: '0.2rem 0.5rem',
                  fontSize: '0.72rem',
                  cursor: 'pointer',
                  fontWeight: filterLevel === lvl ? '600' : 'normal'
                }}
              >
                {lvl}
              </button>
            ))}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={e => setAutoScroll(e.target.checked)}
                style={{ cursor: 'pointer' }}
              />
              Auto-défilement
            </label>
            <button
              onClick={fetchLogs}
              style={{
                backgroundColor: 'transparent',
                color: '#38bdf8',
                border: 'none',
                cursor: 'pointer',
                fontSize: '0.75rem'
              }}
            >
              🔄 Actualiser
            </button>
          </div>
        </div>

        {/* Terminal Log Output */}
        <div style={{
          flex: 1,
          padding: '1.25rem',
          overflowY: 'auto',
          fontFamily: 'Consolas, Monaco, "Lucida Console", "Liberation Mono", monospace',
          fontSize: '0.82rem',
          lineHeight: '1.6',
          backgroundColor: '#070b14'
        }}>
          {loading && logs.length === 0 ? (
            <div style={{ color: '#64748b', textAlign: 'center', paddingTop: '3rem' }}>
              Initialisation du flux de télémétrie CloudWatch...
            </div>
          ) : logs.length === 0 ? (
            <div style={{ color: '#64748b', textAlign: 'center', paddingTop: '3rem' }}>
              Aucun journal enregistré pour cette instance.
            </div>
          ) : (
            filteredLogs.map((logItem, idx) => {
              const timeStr = logItem.timestamp
                ? new Date(logItem.timestamp).toLocaleTimeString()
                : '00:00:00';

              return (
                <div
                  key={logItem.id || idx}
                  style={{
                    display: 'flex',
                    gap: '0.75rem',
                    marginBottom: '0.35rem',
                    wordBreak: 'break-word',
                    alignItems: 'baseline'
                  }}
                >
                  <span style={{ color: '#475569', userSelect: 'none', minWidth: '70px', fontSize: '0.75rem' }}>
                    {timeStr}
                  </span>
                  <span style={{
                    color: getLevelColor(logItem.level),
                    fontWeight: '700',
                    minWidth: '65px',
                    fontSize: '0.75rem'
                  }}>
                    [{logItem.level || 'INFO'}]
                  </span>
                  {logItem.stage && (
                    <span style={{
                      backgroundColor: '#1e293b',
                      color: '#94a3b8',
                      padding: '0.05rem 0.35rem',
                      borderRadius: '3px',
                      fontSize: '0.72rem'
                    }}>
                      {logItem.stage}
                    </span>
                  )}
                  <span style={{ color: '#e2e8f0', flex: 1 }}>
                    {logItem.message}
                  </span>
                </div>
              );
            })
          )}
          {isLive && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              color: '#38bdf8',
              marginTop: '0.75rem',
              fontSize: '0.78rem'
            }}>
              <span style={{
                display: 'inline-block',
                width: '8px',
                height: '14px',
                backgroundColor: '#38bdf8',
                animation: 'blink 1s infinite'
              }}></span>
              Attente des signaux du nœud Raspberry Pi...
            </div>
          )}
          <div ref={terminalEndRef} />
        </div>

        {/* Footer */}
        <div style={{
          backgroundColor: '#0f172a',
          padding: '0.65rem 1.25rem',
          borderTop: '1px solid #1e293b',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '0.75rem',
          color: '#64748b'
        }}>
          <div>
            Total logs : <strong style={{ color: '#cbd5e1' }}>{logs.length}</strong> événements
          </div>
          <div>
            Dernière synchronisation : {lastRefreshed.toLocaleTimeString()}
          </div>
        </div>
      </div>
    </div>
  );
}
