import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card.tsx"
import { pt } from "@/i18n/pt.ts"

export function SidebarNoticeCard() {
  return (
    <Card size="sm" className="rounded-card shadow-none ring-border">
      <CardHeader>
        <CardTitle className="text-label text-foreground">
          {pt.notice.title}
        </CardTitle>
        <CardDescription className="text-caption text-subtle-foreground">
          {pt.notice.body}
        </CardDescription>
      </CardHeader>
    </Card>
  )
}
