package ma.inpt.cloud.vm;

import jakarta.servlet.http.HttpSession;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import ma.inpt.cloud.auth.dto.ApiResponse;
import ma.inpt.cloud.auth.service.AuthService;
import ma.inpt.cloud.vm.dto.CreateVmRequest;
import ma.inpt.cloud.vm.dto.VmResponse;
import ma.inpt.cloud.vm.service.VmService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

/**
 * REST controller for Virtual Machine provisioning and lifecycle management.
 * All operations are tenant-isolated based on the authenticated session's user ID.
 */
@Slf4j
@RestController
@RequestMapping("/api/vms")
@RequiredArgsConstructor
public class VmController {

    private final VmService vmService;

    private UUID getAuthenticatedUserId(HttpSession session) {
        String rawUserId = (String) session.getAttribute(AuthService.SESSION_USER_ID_KEY);
        if (rawUserId == null) {
            throw new SecurityException("Unauthenticated: please log in first.");
        }
        return UUID.fromString(rawUserId);
    }

    /**
     * POST /api/vms — Provision a new Virtual Machine
     */
    @PostMapping
    public ResponseEntity<ApiResponse<VmResponse>> createVm(
            @Valid @RequestBody CreateVmRequest request,
            HttpSession session) {
        try {
            UUID userId = getAuthenticatedUserId(session);
            VmResponse response = vmService.createVm(request, userId);
            return ResponseEntity.status(HttpStatus.CREATED)
                    .body(ApiResponse.ok("Virtual machine provisioned successfully", response));
        } catch (SecurityException ex) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(ApiResponse.error(ex.getMessage()));
        } catch (IllegalArgumentException ex) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                    .body(ApiResponse.error(ex.getMessage()));
        } catch (Exception ex) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(ApiResponse.error(ex.getMessage()));
        }
    }

    /**
     * GET /api/vms — List all active VMs owned by the current user
     */
    @GetMapping
    public ResponseEntity<ApiResponse<List<VmResponse>>> listVms(HttpSession session) {
        try {
            UUID userId = getAuthenticatedUserId(session);
            List<VmResponse> vms = vmService.listUserVms(userId);
            return ResponseEntity.ok(ApiResponse.ok("VMs retrieved successfully", vms));
        } catch (SecurityException ex) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(ApiResponse.error(ex.getMessage()));
        }
    }

    /**
     * GET /api/vms/{id} — Get details of a specific VM
     */
    @GetMapping("/{id}")
    public ResponseEntity<ApiResponse<VmResponse>> getVm(
            @PathVariable UUID id,
            HttpSession session) {
        try {
            UUID userId = getAuthenticatedUserId(session);
            VmResponse response = vmService.getVm(id, userId);
            return ResponseEntity.ok(ApiResponse.ok("VM details retrieved", response));
        } catch (SecurityException ex) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(ApiResponse.error(ex.getMessage()));
        } catch (IllegalArgumentException ex) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(ApiResponse.error(ex.getMessage()));
        }
    }

    /**
     * POST /api/vms/{id}/start — Power on a stopped VM
     */
    @PostMapping("/{id}/start")
    public ResponseEntity<ApiResponse<VmResponse>> startVm(
            @PathVariable UUID id,
            HttpSession session) {
        try {
            UUID userId = getAuthenticatedUserId(session);
            VmResponse response = vmService.startVm(id, userId);
            return ResponseEntity.ok(ApiResponse.ok("VM started successfully", response));
        } catch (SecurityException ex) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(ApiResponse.error(ex.getMessage()));
        } catch (Exception ex) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                    .body(ApiResponse.error(ex.getMessage()));
        }
    }

    /**
     * POST /api/vms/{id}/stop — Power off a running VM
     */
    @PostMapping("/{id}/stop")
    public ResponseEntity<ApiResponse<VmResponse>> stopVm(
            @PathVariable UUID id,
            HttpSession session) {
        try {
            UUID userId = getAuthenticatedUserId(session);
            VmResponse response = vmService.stopVm(id, userId);
            return ResponseEntity.ok(ApiResponse.ok("VM stopped successfully", response));
        } catch (SecurityException ex) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(ApiResponse.error(ex.getMessage()));
        } catch (Exception ex) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                    .body(ApiResponse.error(ex.getMessage()));
        }
    }

    /**
     * DELETE /api/vms/{id} — Terminate and delete a VM
     */
    @DeleteMapping("/{id}")
    public ResponseEntity<ApiResponse<Void>> deleteVm(
            @PathVariable UUID id,
            HttpSession session) {
        try {
            UUID userId = getAuthenticatedUserId(session);
            vmService.deleteVm(id, userId);
            return ResponseEntity.ok(ApiResponse.ok("VM terminated and resources cleaned up", null));
        } catch (SecurityException ex) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(ApiResponse.error(ex.getMessage()));
        } catch (IllegalArgumentException ex) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(ApiResponse.error(ex.getMessage()));
        }
    }
}
