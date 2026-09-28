"""Safe synthetic enterprise troubleshooting runbook definitions."""

from mcp_rag_agent.it_support.models import ITCategory
from mcp_rag_agent.it_support.runbooks.models import (
    Runbook,
    RunbookStep,
    StepActionType,
)


def create_vpn_runbook() -> Runbook:
    """Runbook 1: Corporate VPN Troubleshooting."""
    steps = {
        "vpn_check_internet": RunbookStep(
            step_id="vpn_check_internet",
            title="Verify Local Internet Connectivity",
            instruction="Disconnect from the VPN client and test if standard public websites (e.g., https://www.google.com) load in your browser.",
            expected_outcome="Internet loads normally without VPN.",
            action_type=StepActionType.DIAGNOSTIC,
            max_retries=1,
            next_step_on_success="vpn_restart_service",
            next_step_on_failure="vpn_local_network_guidance",
        ),
        "vpn_local_network_guidance": RunbookStep(
            step_id="vpn_local_network_guidance",
            title="Resolve Local Wi-Fi or Router Outage",
            instruction="Your local internet appears disconnected. Toggle your device Wi-Fi, verify other household devices, or restart your router. Then re-test.",
            expected_outcome="Local internet restored.",
            action_type=StepActionType.INSTRUCTION,
            max_retries=1,
            next_step_on_success="vpn_check_internet",
            next_step_on_failure="escalated",
        ),
        "vpn_restart_service": RunbookStep(
            step_id="vpn_restart_service",
            title="Restart Corporate VPN Client Service",
            instruction="Open Task Manager (Windows) or Activity Monitor (macOS). End all processes named 'Cisco Secure Client' or 'GlobalProtect', then re-launch the application.",
            expected_outcome="VPN client launches cleanly with gateway prompt.",
            action_type=StepActionType.INSTRUCTION,
            max_retries=1,
            next_step_on_success="vpn_test_gateway",
            next_step_on_failure="vpn_clear_cache",
        ),
        "vpn_clear_cache": RunbookStep(
            step_id="vpn_clear_cache",
            title="Flush VPN Certificate & DNS Cache",
            instruction="Open terminal and execute 'ipconfig /flushdns' (Windows) or 'sudo dscacheutil -flushcache' (macOS). Delete stale profiles in VPN preferences.",
            expected_outcome="DNS cache cleared.",
            action_type=StepActionType.INSTRUCTION,
            max_retries=1,
            next_step_on_success="vpn_test_gateway",
            next_step_on_failure="escalated",
        ),
        "vpn_test_gateway": RunbookStep(
            step_id="vpn_test_gateway",
            title="Connect to Corporate Gateway",
            instruction="Select gateway 'vpn.corp.xyz' (or secondary 'vpn-backup.corp.xyz') and complete MFA authentication.",
            expected_outcome="VPN status indicates 'Connected' with corporate IP assigned.",
            action_type=StepActionType.VERIFICATION,
            max_retries=1,
            next_step_on_success="resolved",
            next_step_on_failure="escalated",
        ),
    }
    return Runbook(
        runbook_id="rb_vpn_troubleshooting",
        title="Corporate VPN Troubleshooting",
        description="Diagnose and resolve connection failures, gateway timeouts, and tunnel errors with the enterprise VPN client.",
        category=ITCategory.VPN,
        version="1.0.0",
        initial_step_id="vpn_check_internet",
        steps=steps,
        tags=["vpn", "network", "remote", "anyconnect", "globalprotect", "tunnel"],
        escalation_team="Network Engineering Tier 2",
    )


def create_wifi_runbook() -> Runbook:
    """Runbook 2: Wi-Fi Troubleshooting."""
    steps = {
        "wifi_toggle_adapter": RunbookStep(
            step_id="wifi_toggle_adapter",
            title="Cycle Wi-Fi Hardware Adapter",
            instruction="Turn Wi-Fi off from your system menu bar or tray, wait 10 seconds, and turn Wi-Fi back on.",
            expected_outcome="Device scans and displays available SSIDs.",
            action_type=StepActionType.DIAGNOSTIC,
            max_retries=1,
            next_step_on_success="wifi_select_network",
            next_step_on_failure="wifi_reset_adapter",
        ),
        "wifi_select_network": RunbookStep(
            step_id="wifi_select_network",
            title="Reconnect to CorpNet-Secure Network",
            instruction="Select 'CorpNet-Secure' (or 'CorpNet-Guest' if testing guest access). When prompted, authenticate with corporate single sign-on credentials.",
            expected_outcome="Device associates with the enterprise Wi-Fi SSID.",
            action_type=StepActionType.INSTRUCTION,
            max_retries=1,
            next_step_on_success="wifi_verify_ip",
            next_step_on_failure="wifi_forget_network",
        ),
        "wifi_forget_network": RunbookStep(
            step_id="wifi_forget_network",
            title="Forget Corrupted Wi-Fi Profile",
            instruction="Open Wi-Fi Settings, select 'Forget Network' for CorpNet-Secure to wipe stale 802.1X certificates, then re-enter your password.",
            expected_outcome="Fresh network authentication handshake.",
            action_type=StepActionType.INSTRUCTION,
            max_retries=1,
            next_step_on_success="wifi_verify_ip",
            next_step_on_failure="wifi_reset_adapter",
        ),
        "wifi_reset_adapter": RunbookStep(
            step_id="wifi_reset_adapter",
            title="Release & Renew DHCP Lease",
            instruction="Execute 'ipconfig /release' followed by 'ipconfig /renew' (or renew DHCP lease in macOS Network Settings).",
            expected_outcome="Fresh internal DHCP lease acquired.",
            action_type=StepActionType.INSTRUCTION,
            max_retries=1,
            next_step_on_success="wifi_verify_ip",
            next_step_on_failure="escalated",
        ),
        "wifi_verify_ip": RunbookStep(
            step_id="wifi_verify_ip",
            title="Verify Valid Subnet IP & Gateway Reachability",
            instruction="Verify your IP is in the 10.x.x.x range (not self-assigned 169.254.x.x) and ping the default gateway.",
            expected_outcome="Valid subnet IP and sub-10ms gateway response.",
            action_type=StepActionType.VERIFICATION,
            max_retries=1,
            next_step_on_success="resolved",
            next_step_on_failure="escalated",
        ),
    }
    return Runbook(
        runbook_id="rb_wifi_troubleshooting",
        title="Enterprise Wi-Fi Troubleshooting",
        description="Diagnose intermittent connectivity, SSID association errors, and DHCP lease failures on office and home Wi-Fi.",
        category=ITCategory.WIFI,
        version="1.0.0",
        initial_step_id="wifi_toggle_adapter",
        steps=steps,
        tags=["wifi", "wi-fi", "wireless", "network", "dhcp", "ssid", "corpnet"],
        escalation_team="Network Operations",
    )


def create_mfa_runbook() -> Runbook:
    """Runbook 3: Multi-Factor Authentication (MFA) Troubleshooting."""
    steps = {
        "mfa_check_clock": RunbookStep(
            step_id="mfa_check_clock",
            title="Check Device Time Synchronization",
            instruction="TOTP 6-digit codes depend on exact clock synchronization. In Google Authenticator or Okta Verify, tap Settings -> Time correction for codes -> Sync now (or enable 'Set time automatically' on mobile OS).",
            expected_outcome="Mobile device clock aligned to NTP server.",
            action_type=StepActionType.DIAGNOSTIC,
            max_retries=1,
            next_step_on_success="mfa_retry_code",
            next_step_on_failure="mfa_backup_method",
        ),
        "mfa_retry_code": RunbookStep(
            step_id="mfa_retry_code",
            title="Enter Synchronized MFA Passcode",
            instruction="Wait for a new 30-second token rotation in your Authenticator app and enter the fresh 6-digit code into the login portal.",
            expected_outcome="MFA passcode accepted and login progresses.",
            action_type=StepActionType.VERIFICATION,
            max_retries=1,
            next_step_on_success="resolved",
            next_step_on_failure="mfa_backup_method",
        ),
        "mfa_backup_method": RunbookStep(
            step_id="mfa_backup_method",
            title="Authenticate via Backup MFA Factor",
            instruction="On the login prompt, click 'Verify with something else' and select SMS backup code, phone call, or FIDO2 hardware security key (YubiKey).",
            expected_outcome="Access granted via secondary factor.",
            action_type=StepActionType.INSTRUCTION,
            max_retries=1,
            next_step_on_success="resolved",
            next_step_on_failure="mfa_request_reset",
        ),
        "mfa_request_reset": RunbookStep(
            step_id="mfa_request_reset",
            title="Identity Verification for MFA Re-enrollment",
            instruction="Self-service MFA recovery failed. You must verify identity via live video or manager attestation before an IT administrator can reset your MFA device.",
            expected_outcome="User identity confirmed by helpdesk.",
            action_type=StepActionType.INSTRUCTION,
            max_retries=0,
            next_step_on_success="escalated",
            next_step_on_failure="escalated",
        ),
    }
    return Runbook(
        runbook_id="rb_mfa_troubleshooting",
        title="Multi-Factor Authentication (MFA) Troubleshooting",
        description="Resolve invalid TOTP codes, authenticator app desynchronization, and push notification failures.",
        category=ITCategory.MFA,
        version="1.0.0",
        initial_step_id="mfa_check_clock",
        steps=steps,
        tags=["mfa", "2fa", "okta", "authenticator", "totp", "yubikey", "identity"],
        escalation_team="Identity & Access Management (IAM)",
    )


def create_password_runbook() -> Runbook:
    """Runbook 4: Password & Account Lockout Procedure."""
    steps = {
        "pwd_check_lockout": RunbookStep(
            step_id="pwd_check_lockout",
            title="Inspect Account Status & Auto-Unlock Timer",
            instruction="Accounts lock for 15 minutes after 5 failed password attempts. Check whether you recently changed passwords on mobile/tablet which might be hammering old credentials.",
            expected_outcome="Background apps with stale passwords suspended.",
            action_type=StepActionType.DIAGNOSTIC,
            max_retries=1,
            next_step_on_success="pwd_self_service_portal",
            next_step_on_failure="pwd_self_service_portal",
        ),
        "pwd_self_service_portal": RunbookStep(
            step_id="pwd_self_service_portal",
            title="Access Self-Service Password Reset Portal",
            instruction="Visit https://password.corp.xyz from a browser (or secondary trusted mobile device) and enter your corporate email.",
            expected_outcome="SSPR reset link or code received.",
            action_type=StepActionType.INSTRUCTION,
            max_retries=1,
            next_step_on_success="pwd_set_compliant_password",
            next_step_on_failure="escalated",
        ),
        "pwd_set_compliant_password": RunbookStep(
            step_id="pwd_set_compliant_password",
            title="Set Compliant New Password",
            instruction="Enter a new password meeting policy: minimum 12 characters, including uppercase, lowercase, numbers, and symbols. Must not match previous 5 passwords.",
            expected_outcome="Password changed successfully.",
            action_type=StepActionType.INSTRUCTION,
            max_retries=1,
            next_step_on_success="pwd_verify_login",
            next_step_on_failure="escalated",
        ),
        "pwd_verify_login": RunbookStep(
            step_id="pwd_verify_login",
            title="Verify Sign-In across Core Services",
            instruction="Sign in to your workstation and corporate portal with the new password. Ensure mobile email app credentials are also updated.",
            expected_outcome="Workstation and portal sign-in verified.",
            action_type=StepActionType.VERIFICATION,
            max_retries=1,
            next_step_on_success="resolved",
            next_step_on_failure="escalated",
        ),
    }
    return Runbook(
        runbook_id="rb_password_lockout",
        title="Password Reset & Account Lockout Resolution",
        description="Guide employees through account unlock, self-service password reset, and compliance validation.",
        category=ITCategory.PASSWORD,
        version="1.0.0",
        initial_step_id="pwd_check_lockout",
        steps=steps,
        tags=["password", "lockout", "account", "reset", "sspr", "active directory"],
        escalation_team="IT Helpdesk Tier 1",
    )


def create_github_runbook() -> Runbook:
    """Runbook 5: GitHub Enterprise Access & SAML SSO."""
    steps = {
        "gh_check_sso": RunbookStep(
            step_id="gh_check_sso",
            title="Authorize SAML Single Sign-On",
            instruction="Visit https://github.com/orgs/company-xyz. If prompted with 'Single sign-on', click 'Sign in with your identity provider' and approve Okta authentication.",
            expected_outcome="SAML identity provider token linked to personal GitHub handle.",
            action_type=StepActionType.DIAGNOSTIC,
            max_retries=1,
            next_step_on_success="gh_verify_team_membership",
            next_step_on_failure="gh_relink_sso",
        ),
        "gh_relink_sso": RunbookStep(
            step_id="gh_relink_sso",
            title="De-authorize and Re-link SAML SSO Token",
            instruction="Navigate to GitHub Settings -> Applications -> Authorized SAML Organizations -> Company XYZ. Revoke authorization, log out of Okta, and re-authorize SSO.",
            expected_outcome="Clean SSO authorization established.",
            action_type=StepActionType.INSTRUCTION,
            max_retries=1,
            next_step_on_success="gh_verify_team_membership",
            next_step_on_failure="escalated",
        ),
        "gh_verify_team_membership": RunbookStep(
            step_id="gh_verify_team_membership",
            title="Verify Repository & Team Permissions",
            instruction="Check if you have read/write access to your team's repositories at https://github.com/company-xyz.",
            expected_outcome="Repository visibility and git push/pull access granted.",
            action_type=StepActionType.VERIFICATION,
            max_retries=1,
            next_step_on_success="resolved",
            next_step_on_failure="gh_submit_catalog_request",
        ),
        "gh_submit_catalog_request": RunbookStep(
            step_id="gh_submit_catalog_request",
            title="Submit Team Access Request via Catalog",
            instruction="Your SAML SSO is active but team permissions are unassigned. Open the IT Service Portal, submit 'Developer GitHub Team Request', and specify your engineering manager.",
            expected_outcome="Access request submitted for automated provisioning.",
            action_type=StepActionType.INSTRUCTION,
            max_retries=0,
            next_step_on_success="escalated",
            next_step_on_failure="escalated",
        ),
    }
    return Runbook(
        runbook_id="rb_github_access",
        title="GitHub Enterprise Access & SAML SSO",
        description="Diagnose SAML SSO authentication errors, missing organization memberships, and Git push permissions in GitHub Enterprise.",
        category=ITCategory.ACCESS,
        version="1.0.0",
        initial_step_id="gh_check_sso",
        steps=steps,
        tags=["github", "git", "access", "sso", "saml", "developer_tools"],
        escalation_team="Developer Operations & Platform Security",
    )


def create_jira_runbook() -> Runbook:
    """Runbook 6: Jira & Confluence Access Troubleshooting."""
    steps = {
        "jira_check_okta": RunbookStep(
            step_id="jira_check_okta",
            title="Verify Atlassian Cloud Tile in Okta",
            instruction="Log into your Okta Dashboard at https://corp.okta.com and check if the 'Jira / Atlassian Cloud' tile is visible.",
            expected_outcome="Atlassian tile visible and clickable.",
            action_type=StepActionType.DIAGNOSTIC,
            max_retries=1,
            next_step_on_success="jira_test_project_access",
            next_step_on_failure="jira_request_license",
        ),
        "jira_request_license": RunbookStep(
            step_id="jira_request_license",
            title="Request Jira Product License",
            instruction="You lack an active Atlassian license. Open IT Service Catalog -> Software Requests -> Atlassian Jira Product License.",
            expected_outcome="License approval workflow initiated.",
            action_type=StepActionType.INSTRUCTION,
            max_retries=0,
            next_step_on_success="escalated",
            next_step_on_failure="escalated",
        ),
        "jira_test_project_access": RunbookStep(
            step_id="jira_test_project_access",
            title="Test Target Project & Board Access",
            instruction="Navigate to your target project board (e.g., https://company.atlassian.net/jira/your-board). Check if tickets display or 'Access Denied' is shown.",
            expected_outcome="Project issues and Kanban/Scrum board load cleanly.",
            action_type=StepActionType.VERIFICATION,
            max_retries=1,
            next_step_on_success="resolved",
            next_step_on_failure="jira_request_project_role",
        ),
        "jira_request_project_role": RunbookStep(
            step_id="jira_request_project_role",
            title="Request Project Role Assignment from Lead",
            instruction="You have Atlassian license access, but the project is restricted. Contact the Jira Project Lead or engineering manager to add you to the project role.",
            expected_outcome="Project Lead adds user to Developers or Viewers role.",
            action_type=StepActionType.INSTRUCTION,
            max_retries=1,
            next_step_on_success="resolved",
            next_step_on_failure="escalated",
        ),
    }
    return Runbook(
        runbook_id="rb_jira_access",
        title="Jira & Atlassian Cloud Access Resolution",
        description="Verify Atlassian SSO tiles, product licensing, and project role permissions for Jira Software and Confluence.",
        category=ITCategory.ACCESS,
        version="1.0.0",
        initial_step_id="jira_check_okta",
        steps=steps,
        tags=[
            "jira",
            "confluence",
            "atlassian",
            "access",
            "permissions",
            "collaboration",
        ],
        escalation_team="IT Applications Support",
    )


def create_outlook_runbook() -> Runbook:
    """Runbook 7: Microsoft Outlook & Exchange Online Troubleshooting."""
    steps = {
        "outlook_check_webmail": RunbookStep(
            step_id="outlook_check_webmail",
            title="Verify Webmail (OWA) Access",
            instruction="Open your browser and navigate to https://outlook.office.com. Log in and check if emails send and receive normally.",
            expected_outcome="Webmail functions normally; tenant and account are healthy.",
            action_type=StepActionType.DIAGNOSTIC,
            max_retries=1,
            next_step_on_success="outlook_safe_mode",
            next_step_on_failure="outlook_tenant_escalate",
        ),
        "outlook_tenant_escalate": RunbookStep(
            step_id="outlook_tenant_escalate",
            title="Report Microsoft 365 Exchange Outage",
            instruction="Webmail is also failing. Check the M365 health dashboard or escalate immediately for tenant-wide Exchange Online issues.",
            expected_outcome="Exchange service incident reported.",
            action_type=StepActionType.DIAGNOSTIC,
            max_retries=0,
            next_step_on_success="escalated",
            next_step_on_failure="escalated",
        ),
        "outlook_safe_mode": RunbookStep(
            step_id="outlook_safe_mode",
            title="Launch Outlook in Safe Mode",
            instruction="Press 'Win + R', enter 'outlook.exe /safe' (or hold Option key while opening on macOS) to run without third-party COM add-ins.",
            expected_outcome="Outlook launches without freezing or crashing.",
            action_type=StepActionType.INSTRUCTION,
            max_retries=1,
            next_step_on_success="outlook_disable_faulty_addins",
            next_step_on_failure="outlook_rebuild_profile",
        ),
        "outlook_disable_faulty_addins": RunbookStep(
            step_id="outlook_disable_faulty_addins",
            title="Disable Problematic COM Add-ins",
            instruction="Go to File -> Options -> Add-ins -> COM Add-ins -> Go. Uncheck non-essential add-ins (e.g. legacy conferencing or PDF plugins) and restart Outlook normally.",
            expected_outcome="Outlook operates stably in standard mode.",
            action_type=StepActionType.INSTRUCTION,
            max_retries=1,
            next_step_on_success="resolved",
            next_step_on_failure="outlook_rebuild_profile",
        ),
        "outlook_rebuild_profile": RunbookStep(
            step_id="outlook_rebuild_profile",
            title="Rebuild Outlook Profile & Re-sync OST",
            instruction="Open Control Panel -> Mail -> Show Profiles. Create a fresh profile named 'CorpMail' and allow Exchange to re-cache your mailbox.",
            expected_outcome="Fresh OST file cached from Exchange Online.",
            action_type=StepActionType.VERIFICATION,
            max_retries=1,
            next_step_on_success="resolved",
            next_step_on_failure="escalated",
        ),
    }
    return Runbook(
        runbook_id="rb_outlook_troubleshooting",
        title="Microsoft Outlook & Exchange Troubleshooting",
        description="Triage Outlook client crashes, corrupted OST cache files, faulty COM add-ins, and Exchange sync errors.",
        category=ITCategory.EMAIL,
        version="1.0.0",
        initial_step_id="outlook_check_webmail",
        steps=steps,
        tags=["outlook", "email", "exchange", "m365", "office", "ost"],
        escalation_team="M365 Collaboration Team",
    )


def create_printer_runbook() -> Runbook:
    """Runbook 8: Enterprise & Office Printer Troubleshooting."""
    steps = {
        "printer_check_network": RunbookStep(
            step_id="printer_check_network",
            title="Check Printer Power & Network Reachability",
            instruction="Verify the printer display is on and showing no paper jam or door open warnings. Check that the printer is connected to Ethernet or corporate Wi-Fi.",
            expected_outcome="Printer online with ready status indicator.",
            action_type=StepActionType.DIAGNOSTIC,
            max_retries=1,
            next_step_on_success="printer_clear_queue",
            next_step_on_failure="printer_restart_spooler",
        ),
        "printer_clear_queue": RunbookStep(
            step_id="printer_clear_queue",
            title="Clear Stale & Paused Print Jobs",
            instruction="Open Printers & Scanners -> Select Printer -> Open Queue. Cancel any print jobs showing 'Error - Printing' or 'Paused'.",
            expected_outcome="Queue empty and ready for incoming spools.",
            action_type=StepActionType.INSTRUCTION,
            max_retries=1,
            next_step_on_success="printer_send_test_page",
            next_step_on_failure="printer_restart_spooler",
        ),
        "printer_restart_spooler": RunbookStep(
            step_id="printer_restart_spooler",
            title="Restart Print Spooler Service",
            instruction="Open PowerShell as Admin and execute: 'net stop spooler; Remove-Item $env:SystemRoot\\System32\\Spool\\Printers\\* -Force; net start spooler'.",
            expected_outcome="Print spooler service restarted and spool directory purged.",
            action_type=StepActionType.INSTRUCTION,
            max_retries=1,
            next_step_on_success="printer_send_test_page",
            next_step_on_failure="escalated",
        ),
        "printer_send_test_page": RunbookStep(
            step_id="printer_send_test_page",
            title="Print Internal Test Page",
            instruction="In Printer Properties, click 'Print Test Page' to verify hardware driver communication.",
            expected_outcome="Test page printed cleanly.",
            action_type=StepActionType.VERIFICATION,
            max_retries=1,
            next_step_on_success="resolved",
            next_step_on_failure="escalated",
        ),
    }
    return Runbook(
        runbook_id="rb_printer_troubleshooting",
        title="Enterprise Printer & Spooler Troubleshooting",
        description="Diagnose stuck print queues, offline printer states, driver spooler crashes, and network print failures.",
        category=ITCategory.HARDWARE,
        version="1.0.0",
        initial_step_id="printer_check_network",
        steps=steps,
        tags=["printer", "hardware", "spooler", "print queue", "paper jam"],
        escalation_team="On-site Workplace Services",
    )


def create_laptop_display_runbook() -> Runbook:
    """Runbook 9: Laptop Display & External Monitor Resolution."""
    steps = {
        "disp_check_cables_dock": RunbookStep(
            step_id="disp_check_cables_dock",
            title="Inspect Display Cables & Docking Station",
            instruction="Unplug and firmly reseat both ends of the HDMI, DisplayPort, or USB-C Thunderbolt cable. Ensure the external monitor power LED is blue or green (not flashing amber).",
            expected_outcome="Monitor detects active video input signal.",
            action_type=StepActionType.DIAGNOSTIC,
            max_retries=1,
            next_step_on_success="disp_project_settings",
            next_step_on_failure="disp_power_cycle_dock",
        ),
        "disp_power_cycle_dock": RunbookStep(
            step_id="disp_power_cycle_dock",
            title="Power-Cycle Thunderbolt Dock",
            instruction="Unplug the power brick from your docking station (Dell, HP, or CalDigit dock). Wait 15 seconds, reconnect power, and plug the USB-C cable back into your laptop.",
            expected_outcome="Docking station power re-initialized.",
            action_type=StepActionType.INSTRUCTION,
            max_retries=1,
            next_step_on_success="disp_project_settings",
            next_step_on_failure="disp_restart_graphics_driver",
        ),
        "disp_project_settings": RunbookStep(
            step_id="disp_project_settings",
            title="Configure Display Projection Mode",
            instruction="Press 'Win + P' (Windows) and select 'Extend' (or check System Settings -> Displays on macOS to detect external monitors).",
            expected_outcome="Desktop extends across laptop and external screen.",
            action_type=StepActionType.INSTRUCTION,
            max_retries=1,
            next_step_on_success="disp_verify_resolution",
            next_step_on_failure="disp_restart_graphics_driver",
        ),
        "disp_restart_graphics_driver": RunbookStep(
            step_id="disp_restart_graphics_driver",
            title="Refresh Display Driver via Shortcut",
            instruction="Press 'Win + Ctrl + Shift + B' to restart your GPU graphics subsystem. The screen will flicker and beep once.",
            expected_outcome="Display driver pipeline refreshed.",
            action_type=StepActionType.INSTRUCTION,
            max_retries=1,
            next_step_on_success="disp_verify_resolution",
            next_step_on_failure="escalated",
        ),
        "disp_verify_resolution": RunbookStep(
            step_id="disp_verify_resolution",
            title="Verify Display Refresh Rate & Resolution",
            instruction="Ensure the display is rendering at native resolution (e.g. 1920x1080 or 3840x2160 at 60Hz) with no jitter.",
            expected_outcome="Stable, clear display image without flickering.",
            action_type=StepActionType.VERIFICATION,
            max_retries=1,
            next_step_on_success="resolved",
            next_step_on_failure="escalated",
        ),
    }
    return Runbook(
        runbook_id="rb_laptop_display",
        title="Laptop Display & External Monitor Troubleshooting",
        description="Resolve black screen, external monitor detection failure, dock handshake issues, and display driver crashes.",
        category=ITCategory.HARDWARE,
        version="1.0.0",
        initial_step_id="disp_check_cables_dock",
        steps=steps,
        tags=["display", "monitor", "dock", "hdmi", "usb-c", "thunderbolt", "hardware"],
        escalation_team="Desktop Support Tier 2",
    )


def create_phishing_incident_runbook() -> Runbook:
    """Runbook 10: Phishing & Security Incident Containment."""
    steps = {
        "sec_disconnect_network": RunbookStep(
            step_id="sec_disconnect_network",
            title="Immediate Host Network Isolation",
            instruction="CRITICAL SAFETY ACTION: Immediately turn OFF Wi-Fi and UNPLUG your Ethernet cable to contain potential lateral movement. Do not turn off the machine (preserves volatile memory).",
            expected_outcome="Host isolated from enterprise network.",
            action_type=StepActionType.DIAGNOSTIC,
            max_retries=0,
            next_step_on_success="sec_identify_compromise",
            next_step_on_failure="sec_force_escalate",
        ),
        "sec_identify_compromise": RunbookStep(
            step_id="sec_identify_compromise",
            title="Assess Type of Security Interaction",
            instruction="Did you enter credentials (password/MFA), download and open an attachment, or only click a link? Report the exact suspicious URL or sender address.",
            expected_outcome="Compromise vector categorized.",
            action_type=StepActionType.DIAGNOSTIC,
            max_retries=1,
            next_step_on_success="sec_revoke_sessions",
            next_step_on_failure="sec_force_escalate",
        ),
        "sec_revoke_sessions": RunbookStep(
            step_id="sec_revoke_sessions",
            title="Terminate Okta Sessions & Force Password Reset",
            instruction="Using an uncompromised secondary device, navigate to https://security.corp.xyz/revoke-sessions or contact IT SecOps to force an immediate session revocation across all enterprise tokens.",
            expected_outcome="All active refresh tokens and OAuth sessions invalidated.",
            action_type=StepActionType.INSTRUCTION,
            max_retries=1,
            next_step_on_success="sec_run_edr_triage",
            next_step_on_failure="sec_force_escalate",
        ),
        "sec_run_edr_triage": RunbookStep(
            step_id="sec_run_edr_triage",
            title="Trigger EDR Endpoint Scan & Triage",
            instruction="Security Operations Center (SOC) has initiated a CrowdStrike Falcon on-demand scan. Allow the scan to complete and confirm remediation status.",
            expected_outcome="EDR agent confirms no active backdoors or malicious binaries running.",
            action_type=StepActionType.VERIFICATION,
            max_retries=1,
            next_step_on_success="resolved",
            next_step_on_failure="escalated",
        ),
        "sec_force_escalate": RunbookStep(
            step_id="sec_force_escalate",
            title="P1 Security Escalation to SOC On-Call",
            instruction="Credential compromise or active payload execution detected. An emergency P1 security incident is logged with the SOC Incident Response team.",
            expected_outcome="Direct handoff to Information Security Incident Commander.",
            action_type=StepActionType.INSTRUCTION,
            max_retries=0,
            next_step_on_success="escalated",
            next_step_on_failure="escalated",
        ),
    }
    return Runbook(
        runbook_id="rb_phishing_incident",
        title="Phishing & Security Incident Containment",
        description="Emergency containment workflow for employee phishing interaction, suspicious links, credential theft, and malware.",
        category=ITCategory.SECURITY,
        version="1.0.0",
        initial_step_id="sec_disconnect_network",
        steps=steps,
        tags=[
            "security",
            "phishing",
            "malware",
            "incident",
            "breach",
            "compromise",
            "soc",
        ],
        escalation_team="Security Operations Center (SOC) IR",
    )


def get_all_standard_runbooks() -> list[Runbook]:
    """Return all 10 standard synthetic enterprise runbooks."""
    factories = [
        create_vpn_runbook,
        create_wifi_runbook,
        create_mfa_runbook,
        create_password_runbook,
        create_github_runbook,
        create_jira_runbook,
        create_outlook_runbook,
        create_printer_runbook,
        create_laptop_display_runbook,
        create_phishing_incident_runbook,
    ]
    runbooks = [f() for f in factories]
    # Validate each runbook transition graph integrity upon creation
    for rb in runbooks:
        rb.validate_graph()
    return runbooks
