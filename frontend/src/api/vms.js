import apiClient from './auth.js';

/**
 * Fetch all Virtual Machines for the logged in user
 */
export function getVms() {
  return apiClient.get('/vms');
}

/**
 * Fetch details of a specific VM
 */
export function getVmById(id) {
  return apiClient.get(`/vms/${id}`);
}

/**
 * Request provisioning of a new VM
 */
export function createVm(vmData) {
  return apiClient.post('/vms', vmData);
}

/**
 * Power on a stopped VM
 */
export function startVm(id) {
  return apiClient.post(`/vms/${id}/start`);
}

/**
 * Power off a running VM
 */
export function stopVm(id) {
  return apiClient.post(`/vms/${id}/stop`);
}

/**
 * Terminate and clean up a VM
 */
export function deleteVm(id) {
  return apiClient.delete(`/vms/${id}`);
}

/**
 * Fetch live AWS CloudWatch-style provisioning and lifecycle logs
 */
export function getVmLogs(id) {
  return apiClient.get(`/vms/${id}/logs`);
}

/**
 * Execute command via Web SSH terminal
 */
export function executeVmCommand(id, command) {
  return apiClient.post(`/vms/${id}/exec`, { command });
}
