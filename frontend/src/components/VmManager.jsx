import React, { useState, useEffect } from 'react';
import { getVms, createVm, startVm, stopVm, deleteVm } from '../api/vms.js';
import VmLiveLogsModal from './VmLiveLogsModal.jsx';
import VmTerminalModal from './VmTerminalModal.jsx';

const INPT_BLUE    = '#003366';
const INPT_BLUE_LT = '#004a99';
const SUCCESS_GREEN = '#28a745';
const WARNING_ORANGE = '#f39c12';
const DANGER_RED   = '#e74c3c';
const BG_GRAY      = '#f8fafc';
const BORDER_COLOR = '#e2e8f0';

export default function VmManager() {
  const [vms, setVms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoadingId, setActionLoadingId] = useState(null);

  // Live Logs and Terminal Modals
  const [logsVm, setLogsVm] = useState(null);
  const [terminalVm, setTerminalVm] = useState(null);

  // Modal creation state
  const [showModal, setShowModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  // Form fields
  const [name, setName] = useState('');
  const [os, setOs] = useState('Ubuntu 22.04 LTS');
  const [cpu, setCpu] = useState(1);
  const [ramMb, setRamMb] = useState(512);
  const [diskGb, setDiskGb] = useState(5);
  const [accessMode, setAccessMode] = useState('password'); // 'ssh' or 'password'
  const [sshPublicKey, setSshPublicKey] = useState('');
  const [initialPassword, setInitialPassword] = useState('');
  const [selectedPorts, setSelectedPorts] = useState([22, 80]);

  useEffect(() => {
    loadVms(true);
  }, []);

  // Auto-polling when at least one VM is being provisioned
  useEffect(() => {
    const hasProvisioning = vms.some(v => v.status === 'PROVISIONING' || v.status === 'PENDING');
    if (!hasProvisioning) return;

    const interval = setInterval(() => {
      loadVms(false); // background refresh without resetting loading spinner
    }, 2000);

    return () => clearInterval(interval);
  }, [vms]);

  async function loadVms(showSpinner = true) {
    if (showSpinner) setLoading(true);
    setError('');
    try {
      const res = await getVms();
      const list = res.data?.data || res.data || [];
      setVms(list);
    } catch (err) {
      setError(err?.response?.data?.message || 'Erreur lors du chargement des VM.');
    } finally {
      if (showSpinner) setLoading(false);
    }
  }

  async function handleCreateVm(e) {
    e.preventDefault();
    setFormError('');

    if (!name.trim()) {
      setFormError('Le nom de la machine virtuelle est requis.');
      return;
    }
    if (accessMode === 'password' && !initialPassword.trim()) {
      setFormError('Veuillez renseigner un mot de passe administrateur initial.');
      return;
    }
    if (accessMode === 'ssh' && !sshPublicKey.trim()) {
      setFormError('Veuillez renseigner une clé publique SSH valide.');
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        name: name.trim(),
        os,
        cpu: Number(cpu),
        ramMb: Number(ramMb),
        diskGb: Number(diskGb),
        sshPublicKey: accessMode === 'ssh' ? sshPublicKey.trim() : null,
        initialPassword: accessMode === 'password' ? initialPassword : null,
        openPorts: selectedPorts,
      };

      const res = await createVm(payload);
      setShowModal(false);
      // Reset form
      setName('');
      setInitialPassword('');
      setSshPublicKey('');

      const created = res.data?.data || res.data;
      if (created && created.id) {
        setLogsVm(created); // Automatically open live logs view like AWS CloudWatch
      }
      await loadVms();
    } catch (err) {
      setFormError(err?.response?.data?.message || 'Échec du provisionnement de la machine virtuelle.');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleStart(id) {
    setActionLoadingId(id);
    try {
      await startVm(id);
      await loadVms();
    } catch (err) {
      alert(err?.response?.data?.message || 'Impossible de démarrer la VM');
    } finally {
      setActionLoadingId(null);
    }
  }

  async function handleStop(id) {
    setActionLoadingId(id);
    try {
      await stopVm(id);
      await loadVms();
    } catch (err) {
      alert(err?.response?.data?.message || "Impossible d'arrêter la VM");
    } finally {
      setActionLoadingId(null);
    }
  }

  async function handleDelete(id, vmName) {
    if (!window.confirm(`Confirmez-vous la suppression et le nettoyage de la VM "${vmName}" ?`)) {
      return;
    }
    setActionLoadingId(id);
    try {
      await deleteVm(id);
      await loadVms();
    } catch (err) {
      alert(err?.response?.data?.message || 'Impossible de supprimer la VM');
    } finally {
      setActionLoadingId(null);
    }
  }

  function togglePort(p) {
    if (selectedPorts.includes(p)) {
      setSelectedPorts(selectedPorts.filter(x => x !== p));
    } else {
      setSelectedPorts([...selectedPorts, p]);
    }
  }

  function getStatusBadge(status, vmItem) {
    switch (status) {
      case 'RUNNING':
        return (
          <span style={{ backgroundColor: '#d4edda', color: '#155724', padding: '0.25rem 0.65rem', borderRadius: '12px', fontSize: '0.78rem', fontWeight: '700', display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: SUCCESS_GREEN }}></span> Actif (Running)
          </span>
        );
      case 'PROVISIONING':
      case 'PENDING':
        return (
          <span
            onClick={() => vmItem && setLogsVm(vmItem)}
            style={{
              backgroundColor: '#fff3cd',
              color: '#856404',
              padding: '0.25rem 0.65rem',
              borderRadius: '12px',
              fontSize: '0.78rem',
              fontWeight: '700',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
              cursor: 'pointer',
              border: '1px solid #ffeeba'
            }}
            title="Cliquer pour voir le flux de logs en direct (AWS CloudWatch)"
          >
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: WARNING_ORANGE, display: 'inline-block' }}></span>
            Déploiement en cours (Logs ⚡)
          </span>
        );
      case 'STOPPED':
        return (
          <span style={{ backgroundColor: '#e2e3e5', color: '#383d41', padding: '0.25rem 0.65rem', borderRadius: '12px', fontSize: '0.78rem', fontWeight: '700' }}>
            ⏹ Arrêtée (Stopped)
          </span>
        );
      case 'FAILED':
        return (
          <span
            onClick={() => vmItem && setLogsVm(vmItem)}
            style={{
              backgroundColor: '#f8d7da',
              color: '#721c24',
              padding: '0.25rem 0.65rem',
              borderRadius: '12px',
              fontSize: '0.78rem',
              fontWeight: '700',
              cursor: 'pointer',
              border: '1px solid #f5c6cb'
            }}
            title="Cliquer pour inspecter les logs d'échec"
          >
            ⚠ Échec (Voir logs)
          </span>
        );
      default:
        return <span>{status}</span>;
    }
  }

  return (
    <div style={{ marginTop: '2rem' }}>
      {/* Top action bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ margin: 0, color: INPT_BLUE, fontSize: '1.35rem', fontWeight: '700' }}>
            Mes Machines Virtuelles
          </h2>
          <p style={{ margin: '0.25rem 0 0 0', color: '#718096', fontSize: '0.85rem' }}>
            Cluster Raspberry Pi (Master + Slaves) • {vms.length}/5 VMs actives
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <a
            href="https://master.aslouneyahya.com/dashboard"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              backgroundColor: '#0f172a',
              color: '#38bdf8',
              border: '1px solid #1e293b',
              borderRadius: '8px',
              padding: '0.65rem 1.1rem',
              fontWeight: '600',
              fontSize: '0.85rem',
              textDecoration: 'none',
              display: 'flex',
              alignItems: 'center',
              gap: '0.45rem',
              boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
            }}
            title="Ouvrir le tableau de bord matériel Master Node sur le Raspberry Pi"
          >
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#10b981', display: 'inline-block' }}></span>
            <span>📊 Dashboard Master Node</span>
            <span style={{ fontSize: '0.75rem', opacity: 0.8 }}>↗</span>
          </a>

          <button
            onClick={() => setShowModal(true)}
            style={{
              backgroundColor: INPT_BLUE,
              color: '#fff',
              border: 'none',
              borderRadius: '8px',
              padding: '0.65rem 1.25rem',
              fontWeight: '600',
              fontSize: '0.9rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              boxShadow: '0 2px 6px rgba(0,51,102,0.2)'
            }}
          >
            <span>+</span> Déployer une nouvelle VM
          </button>
        </div>
      </div>

      {error && (
        <div style={{ padding: '0.75rem 1rem', backgroundColor: '#fdecea', color: DANGER_RED, borderRadius: '8px', marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      {/* VM List */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '3rem', color: '#718096' }}>
          Chargement des machines virtuelles...
        </div>
      ) : vms.length === 0 ? (
        <div style={{ backgroundColor: '#fff', borderRadius: '12px', padding: '3rem 2rem', textAlign: 'center', border: `1.5px dashed ${BORDER_COLOR}` }}>
          <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>☁</div>
          <h3 style={{ margin: '0 0 0.5rem 0', color: '#2d3748' }}>Aucune machine virtuelle déployée</h3>
          <p style={{ color: '#718096', fontSize: '0.9rem', maxWidth: '400px', margin: '0 auto 1.5rem auto' }}>
            Créez votre première VM en un clic. Elle sera automatiquement provisionnée sur le cluster Raspberry Pi.
          </p>
          <button
            onClick={() => setShowModal(true)}
            style={{ backgroundColor: INPT_BLUE, color: '#fff', border: 'none', borderRadius: '6px', padding: '0.6rem 1.2rem', fontWeight: '600', cursor: 'pointer' }}
          >
            Créer ma première VM
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: '1.25rem' }}>
          {vms.map(vm => (
            <div key={vm.id} style={{ backgroundColor: '#fff', borderRadius: '12px', border: `1px solid ${BORDER_COLOR}`, padding: '1.35rem', boxShadow: '0 2px 8px rgba(0,0,0,0.04)', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
              <div>
                {/* Header card */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.85rem' }}>
                  <div>
                    <h3 style={{ margin: '0 0 0.2rem 0', color: '#1a202c', fontSize: '1.1rem', fontWeight: '700' }}>
                      {vm.name}
                    </h3>
                    <span style={{ fontSize: '0.8rem', color: '#718096' }}>
                      {vm.os}
                    </span>
                  </div>
                  {getStatusBadge(vm.status, vm)}
                </div>

                {/* Specs pills */}
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
                  <span style={{ backgroundColor: BG_GRAY, border: `1px solid ${BORDER_COLOR}`, padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem', color: '#4a5568' }}>
                    💻 {vm.cpu} vCPU
                  </span>
                  <span style={{ backgroundColor: BG_GRAY, border: `1px solid ${BORDER_COLOR}`, padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem', color: '#4a5568' }}>
                    🧠 {vm.ramMb >= 1024 ? `${vm.ramMb / 1024} Go` : `${vm.ramMb} Mo`} RAM
                  </span>
                  <span style={{ backgroundColor: BG_GRAY, border: `1px solid ${BORDER_COLOR}`, padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem', color: '#4a5568' }}>
                    💾 {vm.diskGb} Go Disque
                  </span>
                </div>

                {/* Network & Access */}
                <div style={{ backgroundColor: '#f7fafc', borderRadius: '8px', padding: '0.75rem', fontSize: '0.82rem', marginBottom: '1rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                    <span style={{ color: '#718096' }}>Adresse IP :</span>
                    <strong style={{ color: vm.ipAddress ? '#2b6cb0' : '#d69e2e', fontFamily: 'monospace' }}>
                      {vm.ipAddress || (vm.status === 'PROVISIONING' ? '⏳ Attribution réseau en cours...' : 'Non attribuée')}
                    </strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                    <span style={{ color: '#718096' }}>Nœud Master/Slave :</span>
                    <span style={{ color: vm.nodeId ? '#2d3748' : '#d69e2e', fontWeight: '500' }}>
                      {vm.nodeId || (vm.status === 'PROVISIONING' ? '⚙ Négociation Master Node...' : 'En attente')}
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#718096' }}>Pare-feu (Ports) :</span>
                    <span style={{ color: '#2d3748', fontWeight: '500' }}>
                      {vm.firewallRules ? vm.firewallRules.split(',').map(p => `:${p}`).join(' ') : ':22'}
                    </span>
                  </div>
                  {vm.ipAddress && vm.status === 'RUNNING' && (
                    <div style={{ marginTop: '0.5rem', paddingTop: '0.5rem', borderTop: '1px dashed #e2e8f0', fontSize: '0.75rem', color: '#4a5568' }}>
                      Accès SSH : <code style={{ backgroundColor: '#edf2f7', padding: '0.15rem 0.4rem', borderRadius: '3px' }}>ssh root@{vm.ipAddress}</code>
                    </div>
                  )}
                  {vm.errorMessage && (
                    <div style={{ marginTop: '0.5rem', color: DANGER_RED, fontSize: '0.75rem' }}>
                      {vm.errorMessage}
                    </div>
                  )}
                </div>
              </div>

              {/* Action buttons */}
              <div style={{ display: 'flex', gap: '0.4rem', paddingTop: '0.65rem', borderTop: `1px solid ${BORDER_COLOR}`, flexWrap: 'wrap', alignItems: 'center' }}>
                {/* AWS Live Logs button */}
                <button
                  onClick={() => setLogsVm(vm)}
                  style={{
                    padding: '0.45rem 0.65rem',
                    backgroundColor: '#f1f5f9',
                    border: `1px solid #cbd5e1`,
                    borderRadius: '6px',
                    fontSize: '0.78rem',
                    cursor: 'pointer',
                    fontWeight: '600',
                    color: '#334155',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.3rem'
                  }}
                  title="Afficher les journaux de déploiement en direct (AWS CloudWatch)"
                >
                  <span>📋</span> Logs {vm.status === 'PROVISIONING' ? '⚡' : ''}
                </button>

                {/* Web SSH Terminal button for RUNNING instances */}
                {vm.status === 'RUNNING' && (
                  <button
                    onClick={() => setTerminalVm(vm)}
                    style={{
                      padding: '0.45rem 0.75rem',
                      backgroundColor: '#0f172a',
                      color: '#38bdf8',
                      border: '1px solid #1e293b',
                      borderRadius: '6px',
                      fontSize: '0.78rem',
                      cursor: 'pointer',
                      fontWeight: '700',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.35rem',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
                    }}
                    title="Ouvrir la console interactive Web SSH"
                  >
                    <span>🖥</span> Console SSH
                  </button>
                )}

                {/* Start / Stop power management */}
                {vm.status === 'RUNNING' && (
                  <button
                    onClick={() => handleStop(vm.id)}
                    disabled={actionLoadingId === vm.id}
                    style={{ flex: 1, minWidth: '70px', padding: '0.45rem', backgroundColor: actionLoadingId === vm.id ? '#edf2f7' : '#fff', border: `1px solid ${BORDER_COLOR}`, borderRadius: '6px', fontSize: '0.78rem', cursor: actionLoadingId === vm.id ? 'wait' : 'pointer', fontWeight: '600', color: '#4a5568' }}
                  >
                    {actionLoadingId === vm.id ? '⏳ Arrêt...' : 'Arrêter'}
                  </button>
                )}
                {vm.status === 'STOPPED' && (
                  <button
                    onClick={() => handleStart(vm.id)}
                    disabled={actionLoadingId === vm.id}
                    style={{ flex: 1, minWidth: '70px', padding: '0.45rem', backgroundColor: actionLoadingId === vm.id ? '#a5d6a7' : SUCCESS_GREEN, color: '#fff', border: 'none', borderRadius: '6px', fontSize: '0.78rem', cursor: actionLoadingId === vm.id ? 'wait' : 'pointer', fontWeight: '600' }}
                  >
                    {actionLoadingId === vm.id ? '⏳ Démarrage...' : 'Démarrer'}
                  </button>
                )}

                {/* Terminate / Delete button */}
                <button
                  onClick={() => handleDelete(vm.id, vm.name)}
                  disabled={actionLoadingId === vm.id}
                  style={{ padding: '0.45rem 0.65rem', backgroundColor: '#fff', border: `1px solid #fed7d7`, borderRadius: '6px', fontSize: '0.78rem', cursor: actionLoadingId === vm.id ? 'wait' : 'pointer', fontWeight: '600', color: DANGER_RED }}
                  title="Supprimer définitivement l'instance"
                >
                  {actionLoadingId === vm.id ? '⏳' : 'Supprimer'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Creation Modal */}
      {showModal && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '1rem' }}>
          <div style={{ backgroundColor: '#fff', borderRadius: '14px', width: '100%', maxWidth: '580px', maxHeight: '90vh', overflowY: 'auto', padding: '2rem', boxShadow: '0 20px 40px rgba(0,0,0,0.2)' }}>
            
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
              <h2 style={{ margin: 0, color: INPT_BLUE, fontSize: '1.25rem', fontWeight: '700' }}>
                Déployer une Machine Virtuelle
              </h2>
              <button
                onClick={() => setShowModal(false)}
                style={{ background: 'none', border: 'none', fontSize: '1.25rem', cursor: 'pointer', color: '#718096' }}
              >
                ✕
              </button>
            </div>

            {formError && (
              <div style={{ padding: '0.75rem', backgroundColor: '#fdecea', color: DANGER_RED, borderRadius: '6px', fontSize: '0.85rem', marginBottom: '1rem' }}>
                {formError}
              </div>
            )}

            <form onSubmit={handleCreateVm}>
              {/* Nom */}
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: '600', color: '#2d3748', marginBottom: '0.35rem' }}>
                  Nom de l'instance
                </label>
                <input
                  type="text"
                  placeholder="ex: web-server-inpt"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  style={{ width: '100%', padding: '0.6rem 0.8rem', border: `1px solid ${BORDER_COLOR}`, borderRadius: '6px', boxSizing: 'border-box' }}
                  required
                />
              </div>

              {/* Système d'exploitation */}
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: '600', color: '#2d3748', marginBottom: '0.35rem' }}>
                  Système d'Exploitation (OS)
                </label>
                <select
                  value={os}
                  onChange={e => setOs(e.target.value)}
                  style={{ width: '100%', padding: '0.6rem 0.8rem', border: `1px solid ${BORDER_COLOR}`, borderRadius: '6px', backgroundColor: '#fff', boxSizing: 'border-box' }}
                >
                  <option value="Ubuntu 22.04 LTS">Ubuntu 22.04 LTS (Jammy Jellyfish)</option>
                  <option value="Debian 12 Bookworm">Debian 12 (Bookworm)</option>
                  <option value="Alpine Linux 3.19">Alpine Linux 3.19 (Léger)</option>
                </select>
              </div>

              {/* Ressources (CPU / RAM / Disque) */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem', marginBottom: '1rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: '600', color: '#4a5568', marginBottom: '0.25rem' }}>
                    CPU (vCPU)
                  </label>
                  <select
                    value={cpu}
                    onChange={e => setCpu(Number(e.target.value))}
                    style={{ width: '100%', padding: '0.55rem', border: `1px solid ${BORDER_COLOR}`, borderRadius: '6px', backgroundColor: '#fff' }}
                  >
                    <option value={1}>1 vCPU (Eco)</option>
                    <option value={2}>2 vCPU (Standard)</option>
                    <option value={3}>3 vCPU (Avancé)</option>
                    <option value={4}>4 vCPU (Max Pi)</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: '600', color: '#4a5568', marginBottom: '0.25rem' }}>
                    Mémoire RAM
                  </label>
                  <select
                    value={ramMb}
                    onChange={e => setRamMb(Number(e.target.value))}
                    style={{ width: '100%', padding: '0.55rem', border: `1px solid ${BORDER_COLOR}`, borderRadius: '6px', backgroundColor: '#fff' }}
                  >
                    <option value={128}>128 Mo (Nano)</option>
                    <option value={256}>256 Mo (Micro)</option>
                    <option value={512}>512 Mo (Léger)</option>
                    <option value={1024}>1 Go (1024 Mo)</option>
                    <option value={2048}>2 Go (2048 Mo)</option>
                    <option value={3072}>3 Go (3072 Mo)</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: '600', color: '#4a5568', marginBottom: '0.25rem' }}>
                    Disque (SSD)
                  </label>
                  <select
                    value={diskGb}
                    onChange={e => setDiskGb(Number(e.target.value))}
                    style={{ width: '100%', padding: '0.55rem', border: `1px solid ${BORDER_COLOR}`, borderRadius: '6px', backgroundColor: '#fff' }}
                  >
                    <option value={1}>1 Go (Micro)</option>
                    <option value={2}>2 Go (Léger)</option>
                    <option value={5}>5 Go (Standard)</option>
                    <option value={10}>10 Go</option>
                    <option value={20}>20 Go</option>
                    <option value={40}>40 Go</option>
                  </select>
                </div>
              </div>

              {/* Méthode d'accès */}
              <div style={{ marginBottom: '1.25rem', backgroundColor: '#f7fafc', padding: '1rem', borderRadius: '8px', border: `1px solid ${BORDER_COLOR}` }}>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: '700', color: '#2d3748', marginBottom: '0.5rem' }}>
                  Authentification & Accès distant (SSH)
                </label>
                <div style={{ display: 'flex', gap: '1rem', marginBottom: '0.75rem' }}>
                  <label style={{ fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.35rem', cursor: 'pointer' }}>
                    <input
                      type="radio"
                      name="access"
                      checked={accessMode === 'password'}
                      onChange={() => setAccessMode('password')}
                    /> Mot de passe initial
                  </label>
                  <label style={{ fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.35rem', cursor: 'pointer' }}>
                    <input
                      type="radio"
                      name="access"
                      checked={accessMode === 'ssh'}
                      onChange={() => setAccessMode('ssh')}
                    /> Clé publique SSH
                  </label>
                </div>

                {accessMode === 'password' ? (
                  <div>
                    <input
                      type="password"
                      placeholder="Définir un mot de passe root (min 8 caractères)"
                      value={initialPassword}
                      onChange={e => setInitialPassword(e.target.value)}
                      style={{ width: '100%', padding: '0.55rem 0.75rem', border: `1px solid ${BORDER_COLOR}`, borderRadius: '6px', boxSizing: 'border-box' }}
                    />
                  </div>
                ) : (
                  <div>
                    <textarea
                      placeholder="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC... user@inpt"
                      value={sshPublicKey}
                      onChange={e => setSshPublicKey(e.target.value)}
                      rows={3}
                      style={{ width: '100%', padding: '0.55rem 0.75rem', border: `1px solid ${BORDER_COLOR}`, borderRadius: '6px', boxSizing: 'border-box', fontFamily: 'monospace', fontSize: '0.78rem' }}
                    />
                  </div>
                )}
              </div>

              {/* Règles de pare-feu */}
              <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: '600', color: '#2d3748', marginBottom: '0.4rem' }}>
                  Règles de pare-feu (Ports d'écoute ouverts)
                </label>
                <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                  {[
                    { port: 22, label: 'SSH (22)' },
                    { port: 80, label: 'HTTP (80)' },
                    { port: 443, label: 'HTTPS (443)' },
                    { port: 8080, label: 'Alt-Web (8080)' }
                  ].map(p => (
                    <label key={p.port} style={{ fontSize: '0.82rem', display: 'flex', alignItems: 'center', gap: '0.35rem', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={selectedPorts.includes(p.port)}
                        onChange={() => togglePort(p.port)}
                      /> {p.label}
                    </label>
                  ))}
                </div>
              </div>

              {/* Action buttons */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  disabled={submitting}
                  style={{ padding: '0.65rem 1.25rem', backgroundColor: '#fff', border: `1px solid ${BORDER_COLOR}`, borderRadius: '6px', cursor: 'pointer', fontWeight: '600', color: '#718096' }}
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  style={{ padding: '0.65rem 1.4rem', backgroundColor: INPT_BLUE, color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '0.5rem' }}
                >
                  {submitting ? 'Provisionnement sur Raspberry Pi...' : 'Lancer le déploiement'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* AWS CloudWatch Live Logs Modal */}
      {logsVm && (
        <VmLiveLogsModal
          vm={logsVm}
          onClose={() => setLogsVm(null)}
        />
      )}

      {/* Web SSH Terminal Modal */}
      {terminalVm && (
        <VmTerminalModal
          vm={terminalVm}
          onClose={() => setTerminalVm(null)}
        />
      )}
    </div>
  );
}
