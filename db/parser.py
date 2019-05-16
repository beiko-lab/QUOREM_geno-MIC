class Input_Model():
    def __init__(self, name=''):
        #self._id = _id
        self.name = name
    def validate(self):
        if not self.name:
            return False
        return True

class Sample(Input_Model):
    def __init__(self, name=''):
        super().__init__(name=name)
        self.biol_reps = {}
        self.metadata = {}

class Replicate():
    def __init__(self, name=''):
        self.name = name
        self.metadata = {}
    def validate(self):
        if not self.name:
            return False
        return True

class Investigation(Input_Model):
    def __init__(self, name='', description='', institution=''):
        super().__init__(name=name)
        self.description = description
        self.institution = institution
        self.samples = {}

    def validate_self(self):
        if not self._description:
            self._description ="Not Specified"
        if not self._institution:
            self._institution = "Not Specified"
        super.validate_self(self)
    def __str__(self):
        return "investigation number " + str(self.name) + " with " + str(len(list(self.samples.items()))) + " samples"

class Upload_Handler():
    def get_models(self, table, key_map):
        #Remove columns which aren't found in the key map.
        cols = list(key_map.keys())
        table = table[cols]
        #
        invs_seen = {}
        samples_seen = {}
        print(table.head())
        for i in range(len(table.index)):
            datum = table.iloc[i]
            investigations, sample_info, sample_metadata, replicates, replicate_metadata = self.partition_datum(datum, key_map)

        # For now: Look if an investigation is seen yet. If not make one. If yes copy it.
        # Do the same for a sample. Replicates shouldnt be duped so dont need to do that for replicates.
        #   ---Later, make error handling to make sure thats valid.
        #      - Look into more effective/prettier implementations. This works for now

        # Add metadata to the replicates.
        # Add replicates to the sample.
        # Add sample to the Investigation.
        # Update the dicts with id as keys.

        #instantiate investigation
            try:
                if investigations['name'] in invs_seen:
                    inv = invs_seen[investigations['name']]
                else:
                    inv = Investigation(name=investigations['name'])
            except:
                continue
        #validate investigation.
            if not inv.validate():
                continue

        #instantiate sample
            try:
                if sample_info['name'] in samples_seen:
                    samp = samples_seen[sample_info['name']]
                else:
                    samp = Sample(name = sample_info['name'])
            except:
                continue

            if not samp.validate():
                continue

            rep = Replicate(replicates['name'])
            rep.metadata = replicate_metadata

        #Assign the replicate to the sample.
            samp.biol_reps[rep.name] = rep
        #Assign the sample metadata to the sample.
            samp.metadata = sample_metadata
        #Assign the sample to the investigation.
            inv.samples[samp.name] = samp
        #Keep track by storing samples and investigations in the dict.
            invs_seen[inv.name] = inv
            samples_seen[samp.name] = samp
        return invs_seen

    def partition_datum(self, datum, dic):
        sample_stuff = {}
        replicate_stuff = {}
        inv_stuff = {}
        sample_metadata = {}
        replicate_metadata = {}
        errors = {}
        NaNs = []
        for i in datum.index:
            mapped = dic[i]
            info = (mapped[1], datum[i])
            if self.isNaN(info[1]):
                NaNs.append(info)
                continue
            if mapped[0] == 'sample':
                sample_stuff[info[0]] = info[1]
            elif mapped[0] == 'bio_replicate':
                replicate_stuff[info[0]] = info[1]
            elif mapped[0] == 'investigation':
                inv_stuff[info[0]] = info[1]
            elif mapped[0] == 'bio_replicate_metadata':
                replicate_metadata[info[0]] = info[1]
            elif mapped[0] == 'sample_metadata':
                sample_metadata[info[0]] = info[1]
            else:
                print("ERROR: " ,mapped[0], "Not Identified Correctly")
                errors[info[0]] = info[1]
        return inv_stuff, sample_stuff, sample_metadata, replicate_stuff, replicate_metadata

    def isNaN(self, arg):
        #for some reason, NaN does not equal itself in Python. This allows tye agnostic NaN checking
        return arg != arg