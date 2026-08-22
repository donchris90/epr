import { useParams } from "react-router-dom";
import { Card } from "../../../components/ui";
import { useClientProgress, useClientSiteMedia } from "../../hooks";
import { QueryState } from "../../components/QueryState";

/** Progress (item 4): the headline percent-complete rollup
 * (services.get_client_progress_summary), plus recent site diary
 * narratives and photos (services.get_client_site_media) as visual
 * evidence of that progress -- not just a number. */
export default function ProgressTab() {
  const { projectId } = useParams<{ projectId: string }>();
  const progress = useClientProgress(projectId);
  const siteMedia = useClientSiteMedia(projectId);

  return (
    <div>
      <QueryState query={progress} emptyTitle="No schedule activity recorded yet">
        {(data: any) => (
          <Card style={{ marginBottom: 20 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 10 }}>
              <div style={{ fontSize: 14, fontWeight: 600 }}>Overall progress</div>
              <div style={{ fontSize: 24, fontWeight: 700, color: "var(--sf-navy-900)" }}>
                {data.overall_percent_complete != null ? `${data.overall_percent_complete}%` : "Not yet available"}
              </div>
            </div>
            <div style={{ height: 10, borderRadius: 999, background: "var(--sf-paper-dim)", overflow: "hidden" }}>
              <div
                style={{
                  height: "100%",
                  width: `${Math.min(100, Math.max(0, data.overall_percent_complete ?? 0))}%`,
                  background: "var(--sf-amber)",
                }}
              />
            </div>
            <div style={{ display: "flex", gap: 20, fontSize: 12, color: "var(--sf-navy-400)", marginTop: 12 }}>
              <span>{data.activity_count} tracked activities</span>
              <span>{data.critical_activity_count} on the critical path</span>
            </div>
          </Card>
        )}
      </QueryState>

      <h3 style={{ fontSize: 14, marginBottom: 10 }}>Recent site updates</h3>
      <QueryState
        query={siteMedia}
        emptyTitle="No site updates yet"
        isEmpty={(d: any) => !d?.diary_summaries?.length}
        emptyHint="Diary entries and photos from the site will appear here."
      >
        {(data: any) => (
          <div style={{ display: "grid", gap: 12 }}>
            {data.diary_summaries.map((d: any) => {
              return (
                <Card key={d.diary_id}>
                  <div style={{ fontSize: 12, color: "var(--sf-navy-400)", marginBottom: 6 }}>{d.diary_date}</div>
                  <div style={{ fontSize: 13 }}>{d.narrative}</div>
                </Card>
              );
            })}
            {(data.media as any[]).some((m) => m.download_url) && (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: 8 }}>
                {(data.media as any[])
                  .filter((m) => m.download_url && m.media_type === "photo")
                  .map((m) => (
                    <a key={m.media_id} href={m.download_url} target="_blank" rel="noreferrer">
                      <img
                        src={m.download_url}
                        alt="Site photo"
                        style={{ width: "100%", height: 100, objectFit: "cover", borderRadius: "var(--sf-radius)", border: "1px solid var(--sf-line)" }}
                      />
                    </a>
                  ))}
              </div>
            )}
          </div>
        )}
      </QueryState>
    </div>
  );
}
