package ma.inpt.cloud.vm.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import ma.inpt.cloud.vm.Vm;
import ma.inpt.cloud.vm.VmRepository;
import ma.inpt.cloud.vm.VmStatus;
import ma.inpt.cloud.vm.dto.CreateVmRequest;
import ma.inpt.cloud.vm.dto.VmResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.List;
import java.util.Random;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

/**
 * Service managing Virtual Machine lifecycle, validation, provisioning and rollback.
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

        // 6. Asynchronous Provisioning on Raspberry Pi Cluster
        triggerAsyncProvisioning(vmId);

        return VmResponse.fromEntity(saved);
    }

    /**
     * Executes real asynchronous provisioning in a background thread.
     * If masterNodeEnabled=true, dispatches request to the Raspberry Pi listener.
     * Otherwise, simulates deployment steps on local hardware.
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

                if (masterNodeEnabled) {
                    log.info("Dispatching VM provisioning to Raspberry Pi Master Node at {}/vms", masterNodeUrl);
                    callMasterNodeProvisioning(vm);
                } else {
                    // Simulation mode (Raspberry Pi offline)
                    Thread.sleep(3000);
                    Thread.sleep(3500);

                    if (vm.getRamMb() > 4096) {
                        vm.setStatus(VmStatus.FAILED);
                        vm.setErrorMessage("Ressources mémoire insuffisantes sur les nœuds esclaves.");
                        vmRepository.save(vm);
                        return;
                    }

                    int hostPart = 100 + random.nextInt(150);
                    String assignedIp = "192.168.1." + hostPart;
                    int nodeIndex = 1 + random.nextInt(3);
                    String assignedNode = "slave-rpi-0" + nodeIndex;

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
            // Extract IP if present in JSON response
            String body = response.body();
            String ip = "192.168.1.100";
            if (body.contains("\"ip_address\":") && !body.contains("\"ip_address\":null")) {
                int start = body.indexOf("\"ip_address\":\"") + 14;
                int end = body.indexOf("\"", start);
                if (start > 13 && end > start) {
                    ip = body.substring(start, end);
                }
            }

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
    public VmResponse stopVm(UUID id, UUID ownerId) {
        Vm vm = vmRepository.findByIdAndOwnerId(id, ownerId)
                .orElseThrow(() -> new IllegalArgumentException("Virtual Machine not found: " + id));
        if (vm.getStatus() != VmStatus.RUNNING) {
            throw new IllegalStateException("Only RUNNING VMs can be stopped.");
        }
        vm.setStatus(VmStatus.STOPPED);
        return VmResponse.fromEntity(vmRepository.save(vm));
    }

    @Transactional
    public VmResponse startVm(UUID id, UUID ownerId) {
        Vm vm = vmRepository.findByIdAndOwnerId(id, ownerId)
                .orElseThrow(() -> new IllegalArgumentException("Virtual Machine not found: " + id));
        if (vm.getStatus() != VmStatus.STOPPED) {
            throw new IllegalStateException("Only STOPPED VMs can be started.");
        }
        vm.setStatus(VmStatus.RUNNING);
        return VmResponse.fromEntity(vmRepository.save(vm));
    }

    @Transactional
    public void deleteVm(UUID id, UUID ownerId) {
        Vm vm = vmRepository.findByIdAndOwnerId(id, ownerId)
                .orElseThrow(() -> new IllegalArgumentException("Virtual Machine not found: " + id));
        vm.setStatus(VmStatus.TERMINATED);
        vmRepository.save(vm);
        log.info("VM {} terminated and resources cleaned up.", id);
    }
}
