package ma.inpt.cloud.vm;

import com.github.f4b6a3.uuid.UuidCreator;
import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * JPA entity representing a Virtual Machine instance on the platform.
 */
@Entity
@Table(name = "virtual_machines", indexes = {
    @Index(name = "idx_vms_owner", columnList = "owner_id"),
    @Index(name = "idx_vms_status", columnList = "status")
})
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Vm {

    @Id
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @Column(name = "name", nullable = false, length = 100)
    private String name;

    @Column(name = "owner_id", nullable = false)
    private UUID ownerId;

    @Column(name = "os", nullable = false, length = 50)
    private String os;

    @Column(name = "cpu", nullable = false)
    private int cpu; // Number of vCPUs

    @Column(name = "ram_mb", nullable = false)
    private int ramMb; // RAM in Megabytes

    @Column(name = "disk_gb", nullable = false)
    private int diskGb; // Storage disk in Gigabytes

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 30)
    @Builder.Default
    private VmStatus status = VmStatus.PENDING;

    @Column(name = "ip_address", length = 45)
    private String ipAddress;

    @Column(name = "ssh_public_key", length = 2048)
    private String sshPublicKey;

    @Column(name = "initial_password", length = 100)
    private String initialPassword;

    @Column(name = "firewall_rules", length = 255)
    private String firewallRules; // e.g. "22,80,443"

    @Column(name = "node_id", length = 50)
    private String nodeId; // e.g. "worker-rpi-01"

    @Column(name = "error_message", length = 500)
    private String errorMessage;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

    @PrePersist
    public void prePersist() {
        if (this.id == null) {
            this.id = UuidCreator.getTimeOrderedEpoch();
        }
        if (this.status == null) {
            this.status = VmStatus.PENDING;
        }
    }
}
