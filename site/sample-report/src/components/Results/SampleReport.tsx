import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import ResultsView from "./ResultsView";

interface ResultType {
  task_id: string;
  metadata: any;
  data: any[];
  status: string;
  error?: string;
}

const SampleReport = () => {
  const { id } = useParams<{ id: string }>();
  const [result, setResult] = useState<ResultType | undefined>(undefined);


  useEffect(() => {
    if (!id) return;

    fetch(`/sample_report_${id}.json`)
      .then(r => {
        if (!r.ok) throw new Error("Failed to fetch JSON");
        return r.json();
      })
      .then(setResult)
      .catch(err => {
        console.error(err);
        setResult(undefined);
      });
  }, [id]);

  return <ResultsView result={result} showSampleBadge />;
}

export default SampleReport;
