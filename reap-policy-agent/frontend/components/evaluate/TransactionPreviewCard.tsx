import type { Transaction, Employee, Vendor, Receipt } from '@/lib/types'

interface Props {
  transaction: Transaction
  employee?: Employee
  vendor?: Vendor
  receipt?: Receipt
}

export function TransactionPreviewCard({ transaction, employee, vendor, receipt }: Props) {
  return (
    <div className="bg-white rounded-lg border border-border divide-y divide-border text-sm">
      <div className="grid grid-cols-2 gap-x-6 px-5 py-4">
        <div>
          <p className="text-xs text-ink-muted mb-1">Amount</p>
          <p className="font-semibold text-ink text-base">{transaction.amount} {transaction.currency}</p>
        </div>
        <div>
          <p className="text-xs text-ink-muted mb-1">Merchant</p>
          <p className="font-medium text-ink">{transaction.merchant_name}</p>
          <p className="text-xs text-ink-muted">MCC {transaction.mcc_code}</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-x-6 px-5 py-4">
        <div>
          <p className="text-xs text-ink-muted mb-1">Employee</p>
          {employee ? (
            <>
              <p className="font-medium text-ink">{employee.name}</p>
              <p className="text-xs text-ink-muted">{employee.department} · {employee.role_level} · {employee.country}</p>
            </>
          ) : (
            <p className="text-ink-muted">{transaction.employee_id}</p>
          )}
        </div>
        <div>
          <p className="text-xs text-ink-muted mb-1">Vendor</p>
          {vendor ? (
            <div className="flex items-center gap-2">
              <p className="font-medium text-ink">{vendor.name}</p>
              {vendor.on_blocklist && (
                <span className="px-1.5 py-0.5 rounded text-xs font-semibold bg-red-100 text-red-700 border border-red-200">
                  BLOCKED
                </span>
              )}
            </div>
          ) : (
            <p className="text-ink-muted text-xs">Unknown vendor</p>
          )}
        </div>
      </div>

      <div className="px-5 py-4 flex items-center gap-6">
        <div>
          <p className="text-xs text-ink-muted mb-1">Receipt</p>
          {receipt ? (
            <span className="text-xs font-medium text-green-700 bg-green-50 border border-green-200 px-2 py-0.5 rounded-full">
              Attached — {receipt.total_amount} {receipt.currency}
            </span>
          ) : (
            <span className="text-xs font-medium text-yellow-700 bg-yellow-50 border border-yellow-200 px-2 py-0.5 rounded-full">
              No receipt
            </span>
          )}
        </div>
        {transaction.description && (
          <div>
            <p className="text-xs text-ink-muted mb-1">Description</p>
            <p className="text-xs text-ink">{transaction.description}</p>
          </div>
        )}
      </div>
    </div>
  )
}
