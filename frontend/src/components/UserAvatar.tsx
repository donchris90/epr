import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "../api/client";

interface MiniProfile {
  email: string;
  avatar_url: string | null;
}

/** Small, real avatar display for the sidebar -- backed by the same
 * GET /v1/auth/me used by the full profile page. Clicking it goes
 * straight to My Profile, matching the common "click your own avatar
 * to manage it" pattern. */
export function UserAvatar() {
  const [profile, setProfile] = useState<MiniProfile | null>(null);

  useEffect(() => {
    apiClient
      .get("/auth/me")
      .then((res) => setProfile(res.data))
      .catch(() => setProfile(null));
  }, []);

  if (!profile) return null;

  return (
    <Link
      to="/settings/profile"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        marginTop: 10,
        textDecoration: "none",
        color: "var(--sf-navy-200)",
      }}
    >
      <div
        style={{
          width: 26,
          height: 26,
          borderRadius: "50%",
          overflow: "hidden",
          background: "var(--sf-navy-700)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 12,
          fontWeight: 700,
          flexShrink: 0,
        }}
      >
        {profile.avatar_url ? (
          <img src={profile.avatar_url} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        ) : (
          profile.email[0].toUpperCase()
        )}
      </div>
      <span style={{ fontSize: 12, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{profile.email}</span>
    </Link>
  );
}
