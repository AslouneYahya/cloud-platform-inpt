package ma.inpt.cloud.vm.dto;

import ma.inpt.cloud.vm.Vm;
import ma.inpt.cloud.vm.VmStatus;

import java.time.LocalDateTime;
import java.util.UUID;

public record VmResponse(
    UUID id,
    String name,
    UUID ownerId,
    String os,
    int cpu,
    int ramMb,
    int diskGb,
    VmStatus status,
    String ipAddress,
    String sshPublicKey,
    boolean hasInitialPassword,
    String firewallRules,
    String nodeId,
    String errorMessage,
    LocalDateTime createdAt,
    LocalDateTime updatedAt
) {
    public static VmResponse fromEntity(Vm vm) {
        return new VmResponse(
            vm.getId(),
            vm.getName(),
            vm.getOwnerId(),
            vm.getOs(),
            vm.getCpu(),
            vm.getRamMb(),
            vm.getDiskGb(),
            vm.getStatus(),
            vm.getIpAddress(),
            vm.getSshPublicKey(),
            vm.getInitialPassword() != null && !vm.getInitialPassword().isBlank(),
            vm.getFirewallRules(),
            vm.getNodeId(),
            vm.getErrorMessage(),
            vm.getCreatedAt(),
            vm.getUpdatedAt()
        );
    }
}
