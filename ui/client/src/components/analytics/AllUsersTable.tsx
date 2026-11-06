import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { AnalyticCard } from "./AnalyticCard";
import { Pagination } from "@/components/shared/Pagination";

interface AllUsersTableProps {
  users: Array<{
    identity_id: string;
    identity_type: string;
    display_name: string;
    run_count: number;
    programs_used: number;
  }>;
  total: number;
  page: number;
  setPage: (updater: (page: number) => number) => void;
  itemsPerPage: number;
}

export function AllUsersTable({ users, total, page, setPage, itemsPerPage }: AllUsersTableProps) {
  const pageCount = Math.ceil(total / itemsPerPage);

  return (
    <AnalyticCard title="Owner activity">
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Identity</TableHead>
              <TableHead className="text-right">Runs</TableHead>
              <TableHead className="text-right">Programs</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.length > 0 ? (
              users.map((user, idx) => (
                <TableRow key={idx} className="hover:bg-muted/50">
                  <TableCell className="font-medium text-sm truncate max-w-[200px]">
                    <span className="flex items-center gap-1.5">
                      {user.identity_type === 'team' && (
                        <span className="text-xs text-blue-400 font-normal">[team]</span>
                      )}
                      {user.display_name || user.identity_id}
                    </span>
                  </TableCell>
                  <TableCell className="text-right text-sm">{user.run_count}</TableCell>
                  <TableCell className="text-right text-sm">{user.programs_used}</TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={3} className="text-center py-6 text-gray-400">
                  No owner activity data available
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      {total > itemsPerPage && (
        <Pagination
          pageIndex={page}
          pageCount={pageCount}
          pageSize={itemsPerPage}
          totalItems={total}
          onPreviousPage={() => setPage((p) => Math.max(0, p - 1))}
          onNextPage={() => setPage((p) => p + 1)}
          canPreviousPage={page > 0}
          canNextPage={page < pageCount - 1}
          itemName="owners"
        />
      )}
    </AnalyticCard>
  );
}
