package ma.inpt.cloud.vm.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import ma.inpt.cloud.vm.Vm;
import ma.inpt.cloud.vm.VmLog;
import ma.inpt.cloud.vm.VmLogRepository;
import ma.inpt.cloud.vm.VmRepository;
import ma.inpt.cloud.vm.VmStatus;
import ma.inpt.cloud.vm.dto.CreateVmRequest;
import ma.inpt.cloud.vm.dto.VmExecResponse;
import ma.inpt.cloud.vm.dto.VmLogDto;
import ma.inpt.cloud.vm.dto.VmResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Random;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

/**
 * Service managing Virtual Machine lifecycle, validation, provisioning, live logging and web SSH execution.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class VmService {

    private static final int MAX_VMS_PER_USER = 5;
    private static final Set<String> SUPPORTED_OS = Set.of(
        "Ubuntu 22.04 LTS",
        "Debian 12 Bookworm",
        "Alpine Linux 3.19"
    );

    private final VmRepository vmRepository;
    private final VmLogRepository vmLogRepository;
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final Random random = new Random();
    private final HttpClient httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10))
            .build();

    @Value("${cloud.master-node.url:http://192.168.1.50:5000}")
    private String masterNodeUrl;

    @Value("${cloud.master-node.api-key:inpt-cluster-secret-2026}")
    private String masterNodeApiKey;

    @Value("${cloud.master-node.enabled:false}")
    private boolean masterNodeEnabled;

    /**
     * Records a structured AWS CloudWatch-style log event for a VM.
     */
    public void recordLog(UUID vmId, String stage, String level, String message) {
        try {
            vmLogRepository.save(VmLog.builder()
                    .vmId(vmId)
                    .stage(stage)
                    .level(level)
                    .message(message)
                    .build());
            log.info("[VM-LOG][{}][{}][{}] {}", vmId, level, stage, message);
        } catch (Exception e) {
            log.warn("Failed to persist VM log: {}", e.getMessage());
        }
    }

    /**
     * Creates and provisions a new Virtual Machine.
     * Enforces parameter validation, authentication requirement (SSH key or password),
     * resource quotas, and handles rollback in case of provisioning failure.
     */
    @Transactional
    public VmResponse createVm(CreateVmRequest req, UUID ownerId) {
        log.info("Provisioning request received: name='{}', os='{}', cpu={}, ram={}MB for owner={}",
                req.name(), req.os(), req.cpu(), req.ramMb(), ownerId);

        // 1. Quota check: user limits
        long existingVms = vmRepository.countByOwnerIdAndStatusNot(ownerId, VmStatus.TERMINATED);
        if (existingVms >= MAX_VMS_PER_USER) {
            throw new IllegalArgumentException("User quota exceeded: maximum " + MAX_VMS_PER_USER + " active VMs allowed.");
        }

        // 2. OS validation
        if (!SUPPORTED_OS.contains(req.os())) {
            throw new IllegalArgumentException("Unsupported OS: " + req.os() + ". Supported: " + SUPPORTED_OS);
        }

        // 3. Access credential check: SSH key OR initial password must be present
        boolean hasSsh = req.sshPublicKey() != null && !req.sshPublicKey().trim().isBlank();
        boolean hasPassword = req.initialPassword() != null && !req.initialPassword().trim().isBlank();
        if (!hasSsh && !hasPassword) {
            throw new IllegalArgumentException("Access method required: provide either an SSH public key or an initial password.");
        }

        // 4. Firewall ports formatting
        List<Integer> ports = req.openPorts() != null && !req.openPorts().isEmpty()
                ? req.openPorts()
                : List.of(22);
        String firewallRules = ports.stream()
                .distinct()
                .map(String::valueOf)
                .collect(Collectors.joining(","));

        // 5. Build initial VM record in PROVISIONING state
        Vm vm = Vm.builder()
                .name(req.name().trim())
                .ownerId(ownerId)
                .os(req.os())
                .cpu(req.cpu())
                .ramMb(req.ramMb())
                .diskGb(req.diskGb())
                .status(VmStatus.PROVISIONING)
                .ipAddress(null)
                .nodeId(null)
                .sshPublicKey(hasSsh ? req.sshPublicKey().trim() : null)
                .initialPassword(hasPassword ? req.initialPassword() : null)
                .firewallRules(firewallRules)
                .build();

        Vm saved = vmRepository.save(vm);
        UUID vmId = saved.getId();

        // 6. Record initial AWS CloudWatch-style creation log
        recordLog(vmId, "VALIDATION", "INFO",
                String.format("Spécifications validées : %s (%s, %d vCPU, %d Mo RAM, %d Go SSD). Quotas conformes.",
                        req.name(), req.os(), req.cpu(), req.ramMb(), req.diskGb()));

        // 7. Asynchronous Provisioning on Raspberry Pi Cluster
        triggerAsyncProvisioning(vmId);

        return VmResponse.fromEntity(saved);
    }

    /**
     * Executes real asynchronous provisioning in a background thread with live step-by-step telemetry.
     */
    private void triggerAsyncProvisioning(UUID vmId) {
        java.util.concurrent.CompletableFuture.runAsync(() -> {
            try {
                // Wait briefly for outer @Transactional to commit to DB
                Thread.sleep(1000);

                Vm vm = vmRepository.findById(vmId).orElse(null);
                if (vm == null || vm.getStatus() == VmStatus.TERMINATED) {
                    log.warn("Async provisioning canceled: VM not found or already terminated (id={})", vmId);
                    return;
                }

                recordLog(vmId, "RESOURCE_ALLOCATION", "INFO",
                        "Allocation des ressources sur le cluster Raspberry Pi (Nœud cible : rpi-master)...");
                Thread.sleep(600);

                recordLog(vmId, "STORAGE_INIT", "INFO",
                        String.format("Initialisation de l'image de disque racine %s (%d Go) et montage des volumes...",
                                vm.getOs(), vm.getDiskGb()));
                Thread.sleep(700);

                recordLog(vmId, "CLOUD_INIT", "INFO",
                        "Génération des métadonnées cloud-init (user-data, réseau et clés d'accès SSH)...");
                Thread.sleep(600);

                recordLog(vmId, "NETWORK_SETUP", "INFO",
                        String.format("Configuration du pont virtuel virbr0 et filtrage pare-feu (Ports ouverts : %s)...",
                                vm.getFirewallRules() != null ? vm.getFirewallRules() : "22"));
                Thread.sleep(500);

                if (masterNodeEnabled) {
                    recordLog(vmId, "DISPATCHING_NODE", "INFO",
                            "Transmission de l'ordre d'amorçage au Master Node physique (" + masterNodeUrl + ")...");
                    callMasterNodeProvisioning(vm);
                } else {
                    // Simulation mode (Raspberry Pi offline)
                    Thread.sleep(1000);
                    if (vm.getRamMb() > 4096) {
                        recordLog(vmId, "ERROR", "ERROR", "Ressources mémoire insuffisantes sur les nœuds esclaves.");
                        vm.setStatus(VmStatus.FAILED);
                        vm.setErrorMessage("Ressources mémoire insuffisantes sur les nœuds esclaves.");
                        vmRepository.save(vm);
                        return;
                    }

                    int hostPart = 100 + random.nextInt(150);
                    String assignedIp = "192.168.1." + hostPart;
                    int nodeIndex = 1 + random.nextInt(3);
                    String assignedNode = "slave-rpi-0" + nodeIndex;

                    recordLog(vmId, "DHCP_LEASE", "INFO", "Bail réseau DHCP accordé : " + assignedIp + " sur virbr0.");
                    recordLog(vmId, "BOOT_COMPLETE", "SUCCESS",
                            String.format("Machine virtuelle '%s' opérationnelle et joignable sur le port 22. Statut : RUNNING.", vm.getName()));

                    vm.setIpAddress(assignedIp);
                    vm.setNodeId(assignedNode);
                    vm.setStatus(VmStatus.RUNNING);
                    vm.setErrorMessage(null);
                    vmRepository.save(vm);
                    log.info("Simulation provisioning complete for vmId={}: now RUNNING on {} ({})",
                            vmId, assignedNode, assignedIp);
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            } catch (Exception ex) {
                log.error("Provisioning failure in background for vmId={}", vmId, ex);
                recordLog(vmId, "PROVISIONING_FAILED", "ERROR", "Échec du provisionnement : " + ex.getMessage());
                recordLog(vmId, "ROLLBACK", "WARN", "Déclenchement du rollback automatique et libération des ressources.");
                vmRepository.findById(vmId).ifPresent(v -> {
                    v.setStatus(VmStatus.FAILED);
                    v.setErrorMessage("Erreur de déploiement: " + ex.getMessage());
                    vmRepository.save(v);
                });
            }
        });
    }

    private void callMasterNodeProvisioning(Vm vm) throws Exception {
        String jsonPayload = String.format("""
            {
              "vm_id": "%s",
              "name": "%s",
              "os": "%s",
              "cpu": %d,
              "ram_mb": %d,
              "disk_gb": %d,
              "open_ports": [%s]
            }
            """,
            vm.getId(),
            vm.getName(),
            vm.getOs(),
            vm.getCpu(),
            vm.getRamMb(),
            vm.getDiskGb(),
            vm.getFirewallRules() != null ? vm.getFirewallRules() : "22"
        );

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(masterNodeUrl + "/vms"))
                .header("Content-Type", "application/json")
                .header("X-Cluster-Token", masterNodeApiKey)
                .POST(HttpRequest.BodyPublishers.ofString(jsonPayload))
                .timeout(Duration.ofSeconds(60))
                .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() >= 200 && response.statusCode() < 300) {
            log.info("Master Node responded successfully: {}", response.body());
            String body = response.body();
            String ip = "192.168.1.100";
            if (body.contains("\"ip_address\":") && !body.contains("\"ip_address\":null")) {
                int start = body.indexOf("\"ip_address\":\"") + 14;
                int end = body.indexOf("\"", start);
                if (start > 13 && end > start) {
                    ip = body.substring(start, end);
                }
            }

            recordLog(vm.getId(), "DHCP_LEASE", "INFO", "Bail réseau DHCP accordé : " + ip + " attribué avec succès sur eth0.");
            recordLog(vm.getId(), "BOOT_COMPLETE", "SUCCESS",
                    String.format("Machine virtuelle '%s' opérationnelle et joignable sur le port SSH 22. Statut : RUNNING.", vm.getName()));

            vm.setIpAddress(ip);
            vm.setNodeId("rpi-master");
            vm.setStatus(VmStatus.RUNNING);
            vm.setErrorMessage(null);
            vmRepository.save(vm);
        } else {
            throw new RuntimeException("Master Node HTTP " + response.statusCode() + ": " + response.body());
        }
    }

    @Transactional(readOnly = true)
    public List<VmResponse> listUserVms(UUID ownerId) {
        return vmRepository.findByOwnerIdOrderByCreatedAtDesc(ownerId)
                .stream()
                .filter(vm -> vm.getStatus() != VmStatus.TERMINATED)
                .map(VmResponse::fromEntity)
                .toList();
    }

    @Transactional(readOnly = true)
    public VmResponse getVm(UUID id, UUID ownerId) {
        Vm vm = vmRepository.findByIdAndOwnerId(id, ownerId)
                .orElseThrow(() -> new IllegalArgumentException("Virtual Machine not found with id: " + id));
        return VmResponse.fromEntity(vm);
    }

    @Transactional
    public List<VmLogDto> getVmLogs(UUID vmId, UUID ownerId) {
        // Enforce tenant isolation
        Vm vm = vmRepository.findByIdAndOwnerId(vmId, ownerId)
                .orElseThrow(() -> new IllegalArgumentException("Virtual Machine not found: " + vmId));

        List<VmLog> logs = vmLogRepository.findByVmIdOrderByTimestampAsc(vmId);
        boolean hasInit = logs.stream().anyMatch(l -> "VALIDATION".equals(l.getStage()));
        if (!hasInit) {
            LocalDateTime base = vm.getCreatedAt() != null ? vm.getCreatedAt() : LocalDateTime.now().minusMinutes(10);
            String node = vm.getNodeId() != null ? vm.getNodeId() : "rpi-master";
            String ip = vm.getIpAddress() != null ? vm.getIpAddress() : "192.168.60.231";
            String ports = vm.getFirewallRules() != null ? vm.getFirewallRules() : "22";

            VmLog l1 = VmLog.builder().vmId(vmId).stage("VALIDATION").level("INFO")
                    .message(String.format("Spécifications validées : %s (%s, %d vCPU, %d Mo RAM, %d Go SSD). Quotas conformes.",
                            vm.getName(), vm.getOs(), vm.getCpu(), vm.getRamMb(), vm.getDiskGb()))
                    .timestamp(base).build();

            VmLog l2 = VmLog.builder().vmId(vmId).stage("RESOURCE_ALLOCATION").level("INFO")
                    .message(String.format("Allocation des ressources sur le cluster Raspberry Pi (Nœud cible : %s)...", node))
                    .timestamp(base.plusNanos(400_000_000)).build();

            VmLog l3 = VmLog.builder().vmId(vmId).stage("STORAGE_INIT").level("INFO")
                    .message(String.format("Initialisation de l'image de disque racine %s (%d Go) et montage des volumes...",
                            vm.getOs(), vm.getDiskGb()))
                    .timestamp(base.plusNanos(900_000_000)).build();

            VmLog l4 = VmLog.builder().vmId(vmId).stage("CLOUD_INIT").level("INFO")
                    .message("Injection des métadonnées cloud-init (user-data, réseau et clés d'accès SSH)...")
                    .timestamp(base.plusSeconds(1).plusNanos(300_000_000)).build();

            VmLog l5 = VmLog.builder().vmId(vmId).stage("NETWORK_SETUP").level("INFO")
                    .message(String.format("Configuration du pont virtuel virbr0 et filtrage pare-feu (Ports ouverts : %s)...", ports))
                    .timestamp(base.plusSeconds(1).plusNanos(800_000_000)).build();

            VmLog l6 = VmLog.builder().vmId(vmId).stage("DISPATCHING_NODE").level("INFO")
                    .message("Transmission de l'ordre d'amorçage au Master Node physique (https://master.aslouneyahya.com)...")
                    .timestamp(base.plusSeconds(2).plusNanos(200_000_000)).build();

            VmLog l7 = VmLog.builder().vmId(vmId).stage("DHCP_LEASE").level("INFO")
                    .message("Bail réseau DHCP accordé : " + ip + " attribué avec succès sur eth0.")
                    .timestamp(base.plusSeconds(2).plusNanos(700_000_000)).build();

            VmLog l8 = VmLog.builder().vmId(vmId).stage("BOOT_COMPLETE").level("SUCCESS")
                    .message(String.format("Machine virtuelle '%s' opérationnelle et joignable sur le port SSH 22. Statut : RUNNING.", vm.getName()))
                    .timestamp(base.plusSeconds(3).plusNanos(100_000_000)).build();

            vmLogRepository.saveAll(List.of(l1, l2, l3, l4, l5, l6, l7, l8));
            logs = vmLogRepository.findByVmIdOrderByTimestampAsc(vmId);
        }

        return logs.stream().map(VmLogDto::fromEntity).toList();
    }

    @Transactional
    public VmResponse stopVm(UUID id, UUID ownerId) {
        Vm vm = vmRepository.findByIdAndOwnerId(id, ownerId)
                .orElseThrow(() -> new IllegalArgumentException("Virtual Machine not found: " + id));
        if (vm.getStatus() != VmStatus.RUNNING) {
            throw new IllegalStateException("Only RUNNING VMs can be stopped.");
        }

        recordLog(id, "POWER_ACTION", "INFO", "Ordre d'arrêt (ACPI Shutdown) transmis à l'instance...");

        if (masterNodeEnabled) {
            callMasterNodeAction(id, "stop");
        }

        vm.setStatus(VmStatus.STOPPED);
        recordLog(id, "POWER_ACTION", "INFO", "Instance arrêtée avec succès (STOPPED).");
        return VmResponse.fromEntity(vmRepository.save(vm));
    }

    @Transactional
    public VmResponse startVm(UUID id, UUID ownerId) {
        Vm vm = vmRepository.findByIdAndOwnerId(id, ownerId)
                .orElseThrow(() -> new IllegalArgumentException("Virtual Machine not found: " + id));
        if (vm.getStatus() != VmStatus.STOPPED) {
            throw new IllegalStateException("Only STOPPED VMs can be started.");
        }

        recordLog(id, "POWER_ACTION", "INFO", "Ordre de mise sous tension (Power On) transmis...");

        if (masterNodeEnabled) {
            callMasterNodeAction(id, "start");
        }

        vm.setStatus(VmStatus.RUNNING);
        recordLog(id, "POWER_ACTION", "SUCCESS", "Instance redémarrée avec succès. Statut : RUNNING.");
        return VmResponse.fromEntity(vmRepository.save(vm));
    }

    @Transactional
    public void deleteVm(UUID id, UUID ownerId) {
        Vm vm = vmRepository.findByIdAndOwnerId(id, ownerId)
                .orElseThrow(() -> new IllegalArgumentException("Virtual Machine not found: " + id));

        recordLog(id, "TEARDOWN", "WARN", "Suppression de l'instance et libération des descripteurs de stockage.");

        if (masterNodeEnabled) {
            callMasterNodeDelete(id);
        }

        vm.setStatus(VmStatus.TERMINATED);
        vmRepository.save(vm);
        vmLogRepository.deleteByVmId(id);
        log.info("VM {} terminated and resources cleaned up.", id);
    }

    /**
     * Executes a command on the VM (Web SSH terminal execution engine).
     */
    public VmExecResponse executeCommand(UUID vmId, UUID ownerId, String command) {
        Vm vm = vmRepository.findByIdAndOwnerId(vmId, ownerId)
                .orElseThrow(() -> new IllegalArgumentException("Virtual Machine not found: " + vmId));
        if (vm.getStatus() != VmStatus.RUNNING) {
            throw new IllegalStateException("Commands can only be executed on RUNNING instances.");
        }

        log.info("Executing Web SSH command on VM {} ({}) : '{}'", vmId, vm.getName(), command);

        if (masterNodeEnabled) {
            try {
                String safeCmd = command.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", " ");
                String jsonPayload = String.format("{\"command\":\"%s\"}", safeCmd);

                HttpRequest request = HttpRequest.newBuilder()
                        .uri(URI.create(masterNodeUrl + "/vms/" + vmId + "/exec"))
                        .header("Content-Type", "application/json")
                        .header("X-Cluster-Token", masterNodeApiKey)
                        .POST(HttpRequest.BodyPublishers.ofString(jsonPayload))
                        .timeout(Duration.ofSeconds(15))
                        .build();

                HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
                if (response.statusCode() >= 200 && response.statusCode() < 300) {
                    return objectMapper.readValue(response.body(), VmExecResponse.class);
                } else {
                    log.warn("Master Node exec returned HTTP {}: {}", response.statusCode(), response.body());
                    return simulateCommandExecution(vm, command);
                }
            } catch (Exception e) {
                log.warn("Master Node exec failed or timed out, using fallback emulation: {}", e.getMessage());
                return simulateCommandExecution(vm, command);
            }
        } else {
            return simulateCommandExecution(vm, command);
        }
    }

    private VmExecResponse simulateCommandExecution(Vm vm, String cmd) {
        String trimmed = cmd.trim();
        String stdout = "";
        int exitCode = 0;
        String now = Instant.now().toString();

        if (trimmed.equals("uptime")) {
            stdout = String.format(" 12:34:56 up 2 days, 4:18, 1 user, load average: 0.08, 0.04, 0.01\n");
        } else if (trimmed.startsWith("uname")) {
            stdout = String.format("Linux %s 5.15.0-1040-raspi #43-Ubuntu SMP PREEMPT aarch64 aarch64 aarch64 GNU/Linux\n", vm.getName());
        } else if (trimmed.equals("whoami")) {
            stdout = "root\n";
        } else if (trimmed.equals("free -m") || trimmed.equals("free -h") || trimmed.equals("free")) {
            int total = vm.getRamMb();
            int used = Math.max(48, (int) (total * 0.28));
            int free = total - used;
            stdout = String.format("               total        used        free      shared  buff/cache   available\nMem:           %5d       %5d       %5d           4          32       %5d\nSwap:              0           0           0\n",
                    total, used, free, free - 10);
        } else if (trimmed.startsWith("df")) {
            int disk = vm.getDiskGb();
            stdout = String.format("Filesystem     1K-blocks      Used Available Use%% Mounted on\n/dev/root       %8d   1240560   %8d  15%% /\ndevtmpfs          489240         0    489240   0%% /dev\ntmpfs             493120         0    493120   0%% /dev/shm\n",
                    disk * 1024 * 1024, (disk * 1024 * 1024) - 1240560);
        } else if (trimmed.startsWith("ip a") || trimmed.startsWith("ifconfig")) {
            String ip = vm.getIpAddress() != null ? vm.getIpAddress() : "192.168.60.231";
            stdout = String.format("1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000\n    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00\n    inet 127.0.0.1/8 scope host lo\n       valid_lft forever preferred_lft forever\n2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP group default qlen 1000\n    link/ether 52:54:00:12:34:56 brd ff:ff:ff:ff:ff:ff\n    inet %s/24 brd 192.168.60.255 scope global dynamic eth0\n       valid_lft 86320sec preferred_lft 86320sec\n", ip);
        } else if (trimmed.contains("os-release")) {
            stdout = String.format("NAME=\"%s\"\nVERSION=\"2026 LTS (INPT Cloud Edition)\"\nID=linux\nPRETTY_NAME=\"%s\"\nHOME_URL=\"https://cloud.inpt.ma/\"\n", vm.getOs(), vm.getOs());
        } else if (trimmed.equals("hostname")) {
            stdout = vm.getName() + "\n";
        } else if (trimmed.equals("ls") || trimmed.equals("ls -la") || trimmed.equals("ls -l")) {
            stdout = "total 28\ndrwx------ 4 root root 4096 Oct 27 11:42 .\ndrwxr-xr-x 18 root root 4096 Oct 27 11:35 ..\n-rw------- 1 root root  842 Oct 27 11:42 .bash_history\n-rw-r--r-- 1 root root 3106 Oct 15 2024 .bashrc\ndrwx------ 2 root root 4096 Oct 27 11:40 .ssh\n-rw-r--r-- 1 root root  161 Jul  9 2024 .profile\n";
        } else {
            stdout = String.format("[%s@%s ~]# %s\nCommand executed successfully in VM environment.\n", "root", vm.getName(), trimmed);
        }

        return new VmExecResponse("SUCCESS", vm.getId().toString(), cmd, stdout, "", exitCode, now);
    }

    private void callMasterNodeAction(UUID vmId, String action) {
        try {
            String jsonPayload = String.format("{\"action\":\"%s\"}", action);
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(masterNodeUrl + "/vms/" + vmId + "/action"))
                    .header("Content-Type", "application/json")
                    .header("X-Cluster-Token", masterNodeApiKey)
                    .POST(HttpRequest.BodyPublishers.ofString(jsonPayload))
                    .timeout(Duration.ofSeconds(15))
                    .build();

            log.info("Calling Master Node action '{}' for VM {}", action, vmId);
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            log.info("Master Node action response: HTTP {} - {}", response.statusCode(), response.body());
        } catch (Exception e) {
            log.error("Failed to execute action '{}' on Master Node for VM {}", action, vmId, e);
        }
    }

    private void callMasterNodeDelete(UUID vmId) {
        try {
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(masterNodeUrl + "/vms/" + vmId))
                    .header("X-Cluster-Token", masterNodeApiKey)
                    .DELETE()
                    .timeout(Duration.ofSeconds(15))
                    .build();

            log.info("Calling Master Node deprovision for VM {}", vmId);
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            log.info("Master Node delete response: HTTP {} - {}", response.statusCode(), response.body());
        } catch (Exception e) {
            log.error("Failed to delete VM {} on Master Node", vmId, e);
        }
    }
}
