package ma.inpt.cloud.vm;

/**
 * Lifecycle states of a Virtual Machine on the cloud platform.
 */
public enum VmStatus {
    PENDING,        // Creation request submitted, awaiting scheduling
    PROVISIONING,   // Allocating resources on Raspberry Pi cluster
    RUNNING,        // Deployed, active and reachable via assigned IP
    STOPPED,        // Powered off by user
    FAILED,         // Provisioning error (resources exceeded or script failure)
    TERMINATED      // Cleaned up and deleted
}
