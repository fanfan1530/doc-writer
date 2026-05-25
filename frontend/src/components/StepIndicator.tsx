interface StepIndicatorProps {
  steps: string[];
  currentStep: number;
  className?: string;
}

export default function StepIndicator({
  steps,
  currentStep,
  className = '',
}: StepIndicatorProps) {
  return (
    <div className={`flex items-center justify-center gap-0 ${className}`}>
      {steps.map((label, i) => (
        <div key={i} className="flex items-center">
          <div className="flex flex-col items-center">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-all duration-300
                ${i < currentStep
                  ? 'bg-emerald-500 text-white shadow-md shadow-emerald-500/25'
                  : i === currentStep
                    ? 'bg-police-600 text-white shadow-lg shadow-police-500/30 ring-4 ring-police-500/20'
                    : 'bg-slate-200 text-slate-500'
                }`}
            >
              {i < currentStep ? (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                i + 1
              )}
            </div>
            <span
              className={`mt-1.5 text-xs whitespace-nowrap transition-colors duration-300
                ${i === currentStep ? 'text-police-600 font-semibold' : 'text-slate-400'}
              `}
            >
              {label}
            </span>
          </div>
          {i < steps.length - 1 && (
            <div
              className={`w-8 sm:w-16 h-0.5 mx-1 mt-[-16px] transition-colors duration-300
                ${i < currentStep ? 'bg-emerald-400' : 'bg-slate-200'}
              `}
            />
          )}
        </div>
      ))}
    </div>
  );
}
